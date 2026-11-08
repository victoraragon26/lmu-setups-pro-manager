import os
import sys
import re
import json
import asyncio
import threading
import datetime
import urllib.request
import webbrowser
import customtkinter as ctk
import tkinter.messagebox as messagebox
from tkinter import filedialog
from telethon import TelegramClient, events

# --- IMPORTS PARA GESTIONAR NOTIFICACIONES ---
# noinspection PyUnresolvedReferences
from telethon.tl.functions.account import UpdateNotifySettingsRequest, GetNotifySettingsRequest
# noinspection PyUnresolvedReferences
from telethon.tl.types import InputPeerNotifySettings, InputNotifyPeer

# --- IMPORTS DE NUESTROS MÓDULOS EXTERNOS (ARQUITECTURA LIMPIA) ---
from lmu_cars import normalizar_coche_texto
from lmu_tracks import obtener_carpeta_circuito
from lmu_parser import extraer_version_archivo, extraer_creador_fallback

# --- 1. CONFIGURACIÓN ---
from credentials import API_ID, API_HASH, BOT_USERNAME

# Carpeta de datos de la aplicación
CARPETA_APP = os.path.join(
    os.getenv("APPDATA"),
    "LMU Setups Pro Manager"
)

os.makedirs(CARPETA_APP, exist_ok=True)

CONFIG_FILE = os.path.join(CARPETA_APP, "config.json")

# --- 1.2 CONFIGURACIÓN DE LA APP Y ACTUALIZACIONES ---
APP_VERSION = "0.1.3"

GITHUB_VERSION_URL = "https://raw.githubusercontent.com/victoraragon26/lmu-setups-pro-manager/main/version.json"
GITHUB_RELEASES_URL = "https://github.com/victoraragon26/lmu-setups-pro-manager/releases"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# Función auxiliar para encontrar recursos (Icono) tanto en local como en el .exe
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# --- 2. VENTANA DE AVISO MODERNA (CUSTOM) ---
class ModernDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, message, is_warning=False):
        super().__init__(parent)
        self.title("Aviso del Sistema")
        self.geometry("480x260")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.result = False

        if parent:
            parent.update_idletasks()
            x = parent.winfo_x() + (parent.winfo_width() - 480) // 2
            y = parent.winfo_y() + (parent.winfo_height() - 260) // 2
            self.geometry(f"+{x}+{y}")

        color = "#d9534f" if is_warning else "#3498db"
        hover = "#c9302c" if is_warning else "#2980b9"

        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.pack(pady=(20, 10), fill="x", padx=20)

        self.lbl_title = ctk.CTkLabel(self.frame_top, text=title, font=("Arial", 18, "bold"), text_color=color)
        self.lbl_title.pack()

        if "no encontrada" in title.lower():
            mensaje_corto = message.split('\n\n')[0]
            self.lbl_msg = ctk.CTkLabel(self, text=mensaje_corto, font=("Arial", 14), wraplength=420, justify="center")
        else:
            self.lbl_msg = ctk.CTkLabel(self, text=message, font=("Arial", 14), wraplength=420, justify="center")

        self.lbl_msg.pack(pady=10, padx=20, expand=True)

        self.frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_btns.pack(pady=(10, 20))

        if "no encontrada" in title.lower() or "información" in title.lower():
            self.btn_ok = ctk.CTkButton(self.frame_btns, text="Entendido", command=self.on_yes, width=120, height=35,
                                        fg_color=color, hover_color=hover, font=("Arial", 13, "bold"))
            self.btn_ok.pack(side="top", pady=10)
        else:
            self.btn_yes = ctk.CTkButton(self.frame_btns, text="Sí", command=self.on_yes, width=120, height=35,
                                         fg_color=color, hover_color=hover, font=("Arial", 13, "bold"))
            self.btn_yes.pack(side="left", padx=15)

            self.btn_no = ctk.CTkButton(self.frame_btns, text="No", command=self.on_no, width=120, height=35,
                                        fg_color="#4a4a4a", hover_color="#333333", font=("Arial", 13, "bold"))
            self.btn_no.pack(side="right", padx=15)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_yes(self):
        self.result = True
        self.destroy()

    def on_no(self):
        self.result = False
        self.destroy()

    def on_close(self):
        self.result = False
        self.destroy()

    def get_input(self):
        self.grab_set()
        self.wait_window()
        return self.result


# --- 3. APLICACIÓN PRINCIPAL ---
class LMUApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"LMU Setups Pro Manager (v{APP_VERSION})")
        self.geometry("800x850")
        self.ruta_destino = ""
        self.bot_is_running = False

        try:
            icon_path = resource_path("LMU_Setups_Pro_Manager.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        self.ultimo_texto_menu = None
        self.subcarpeta_circuito = ""
        self.descarga_en_curso = False
        self.checkboxes_setups = []
        self.meta_db = {}
        self.app_lo_silencio = False

        ruta_sesion = os.path.join(CARPETA_APP, "mi_sesion_lmu")
        self.client = TelegramClient(ruta_sesion, API_ID, API_HASH)

        self.loop = asyncio.new_event_loop()
        self.t_thread = threading.Thread(target=self.start_async_loop, daemon=True)
        self.t_thread.start()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- INTERFAZ SUPERIOR GLOBALES ---
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.pack(pady=10, fill="x", padx=20)

        self.btn_carpeta = ctk.CTkButton(self.frame_top, text="Carpeta LMU", command=self.seleccionar_carpeta,
                                         width=120)
        self.btn_carpeta.grid(row=0, column=0, padx=5)

        self.label_ruta = ctk.CTkLabel(self.frame_top, text="Ruta no seleccionada", text_color="gray", width=250,
                                       anchor="w")
        self.label_ruta.grid(row=0, column=1, padx=5)

        self.btn_iniciar = ctk.CTkButton(self.frame_top, text="Conectar al Bot", fg_color="green",
                                         hover_color="darkgreen", command=self.toggle_bot, width=120)
        self.btn_iniciar.grid(row=0, column=2, padx=5)

        # UI de Login
        self.frame_login = ctk.CTkFrame(self, fg_color="#333333", corner_radius=10)
        self.label_login = ctk.CTkLabel(self.frame_login, text="Inicia sesión en Telegram:", font=("Arial", 14, "bold"))
        self.entry_phone = ctk.CTkEntry(self.frame_login, placeholder_text="Teléfono (ej: +34...)", width=220)
        self.btn_phone = ctk.CTkButton(self.frame_login, text="Enviar Código", command=self.pedir_codigo)
        self.entry_code = ctk.CTkEntry(self.frame_login, placeholder_text="Código SMS/Telegram", width=220)
        self.btn_code = ctk.CTkButton(self.frame_login, text="Iniciar Sesión", command=self.enviar_codigo)

        # --- SISTEMA DE PESTAÑAS (TABS) ---
        self.tabview = ctk.CTkTabview(self, width=750, height=550)
        self.tabview.pack(pady=10, padx=20, fill="both", expand=True)

        self.tab_descargas = self.tabview.add("📥 Descargas")
        self.tab_gestor = self.tabview.add("⚙️ Gestor de Setups")

        # === PESTAÑA 1: DESCARGAS ===
        self.frame_bot_pantalla = ctk.CTkScrollableFrame(self.tab_descargas, fg_color="#1e1e1e", corner_radius=15)
        self.frame_bot_pantalla.pack(pady=10, padx=10, fill="both", expand=True)
        self.label_info = ctk.CTkLabel(self.frame_bot_pantalla, text="Selecciona tu carpeta y conecta para empezar...",
                                       text_color="gray", font=("Arial", 14))
        self.label_info.pack(pady=40)

        # === PESTAÑA 2: GESTOR DE SETUPS ===
        self.top_gestor = ctk.CTkFrame(self.tab_gestor, fg_color="transparent")
        self.top_gestor.pack(fill="x", pady=10)

        self.btn_refresh = ctk.CTkButton(self.top_gestor, text="🔄", command=self.actualizar_lista_circuitos, width=40)
        self.btn_refresh.pack(side="left", padx=2)

        self.combo_circuitos = ctk.CTkOptionMenu(self.top_gestor, values=["Todos los circuitos"],
                                                 command=self.aplicar_filtros_dinamicos, width=150)
        self.combo_circuitos.pack(side="left", padx=2)

        self.combo_coches = ctk.CTkOptionMenu(self.top_gestor, values=["Todos los coches"],
                                              command=self.aplicar_filtros_dinamicos, width=170)
        self.combo_coches.pack(side="left", padx=2)

        self.combo_creadores = ctk.CTkOptionMenu(self.top_gestor, values=["Todos los creadores"],
                                                 command=self.aplicar_filtros_dinamicos, width=170)
        self.combo_creadores.pack(side="left", padx=2)

        self.btn_eliminar = ctk.CTkButton(self.top_gestor, text="🗑️", fg_color="#d9534f", hover_color="#c9302c",
                                          command=self.eliminar_setups, width=40)
        self.btn_eliminar.pack(side="right", padx=2)

        self.btn_seleccionar_todos = ctk.CTkButton(self.top_gestor, text="☑️ Marcar",
                                                   command=self.toggle_seleccionar_todos, width=80)
        self.btn_seleccionar_todos.pack(side="right", padx=2)

        self.frame_lista_setups = ctk.CTkScrollableFrame(self.tab_gestor, fg_color="#2b2b2b", corner_radius=10)
        self.frame_lista_setups.pack(fill="both", expand=True, pady=5, padx=5)

        # Log global inferior
        self.textbox_log = ctk.CTkTextbox(self, width=750, height=100, state="disabled", fg_color="#1a1a1a")
        self.textbox_log.pack(pady=(0, 10), padx=20)

        # Eventos
        self.client.add_event_handler(self.handler_mensajes, events.NewMessage(chats=BOT_USERNAME))
        self.client.add_event_handler(self.handler_mensajes, events.MessageEdited(chats=BOT_USERNAME))

        self.cargar_ruta_guardada()
        self.after(2000, self.verificar_actualizaciones)

    # --- SISTEMA DE VERIFICACIÓN DE ACTUALIZACIONES ---
    def verificar_actualizaciones(self):
        def check():
            try:
                if "TU_USUARIO" in GITHUB_VERSION_URL: return
                req = urllib.request.Request(GITHUB_VERSION_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    version_remota = data.get("version", APP_VERSION)
                    url_descarga = data.get("url", GITHUB_RELEASES_URL)
                    if version_remota > APP_VERSION:
                        self.after(0, lambda: self.mostrar_aviso_actualizacion(version_remota, url_descarga))
            except Exception:
                pass

        threading.Thread(target=check, daemon=True).start()

    def mostrar_aviso_actualizacion(self, version_remota, url_descarga):
        res = ModernDialog(self, "¡Actualización Disponible!",
                           f"Estás usando la versión v{APP_VERSION} y la nueva v{version_remota} ya está disponible.\n\n¿Quieres abrir la página de descargas?",
                           is_warning=False).get_input()
        if res: webbrowser.open(url_descarga)

    # --- FUNCIONES BÁSICAS Y HERRAMIENTAS ---
    def start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def log(self, mensaje):
        def actualizar_texto():
            self.textbox_log.configure(state="normal")
            self.textbox_log.insert("end", mensaje + "\n")
            self.textbox_log.see("end")
            self.textbox_log.configure(state="disabled")

        self.after(0, actualizar_texto)

    def limpiar_texto(self, texto):
        return re.sub(r'[^\w\s\.-]', '', texto).strip().lower()

    def on_closing(self):
        if self.bot_is_running or getattr(self, 'app_lo_silencio', False):
            self.attributes("-alpha", 0.8)
            self.title("Cerrando aplicación y restaurando configuraciones...")
            self.log("Forzando apagado seguro. Restaurando notificaciones...")
            asyncio.run_coroutine_threadsafe(self.cierre_seguro(), self.loop)
        else:
            self.destroy()
            os._exit(0)

    async def cierre_seguro(self):
        if getattr(self, 'app_lo_silencio', False):
            try:
                await self.client(UpdateNotifySettingsRequest(
                    peer=BOT_USERNAME, settings=InputPeerNotifySettings(mute_until=0)
                ))
            except Exception:
                pass
        if self.client.is_connected(): await self.client.disconnect()
        self.after(0, self.destroy)
        os._exit(0)

    # --- FUNCIONES DE CLASIFICACIÓN USANDO MÓDULOS EXTERNOS ---
    def normalizar_coche(self, nombre_sucio):
        return normalizar_coche_texto(nombre_sucio)

    def extraer_coche_fallback(self, filename):
        nombre = filename.replace(".svm", "").replace(".json", "")
        return normalizar_coche_texto(nombre)

    def restaurar_pantalla_inicio(self):
        self.btn_iniciar.configure(text="Conectar al Bot", fg_color="green", state="normal")
        self.tabview.set("📥 Descargas")
        for widget in self.frame_bot_pantalla.winfo_children(): widget.destroy()

        texto_lbl = "Selecciona tu carpeta y conecta para empezar..."
        color_lbl = "gray"
        if self.ruta_destino and os.path.exists(self.ruta_destino):
            texto_lbl = "Carpeta cargada correctamente.\n\nPulsa 'Conectar al Bot' para empezar."
            color_lbl = "#2ecc71"
        self.label_info = ctk.CTkLabel(self.frame_bot_pantalla, text=texto_lbl, text_color=color_lbl,
                                       font=("Arial", 14))
        self.label_info.pack(pady=40)

    def cargar_ruta_guardada(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if 'ruta_setups' in config and os.path.exists(config['ruta_setups']):
                    self.ruta_destino = config['ruta_setups']
                    texto_ruta = ".../" + "/".join(self.ruta_destino.replace("\\", "/").split("/")[-4:])
                    self.label_ruta.configure(text=texto_ruta)
                    self.label_info.configure(
                        text="Carpeta cargada correctamente.\n\nPulsa 'Conectar al Bot' para empezar.",
                        text_color="#2ecc71")
                    self.log("Ruta cargada. Ve al Gestor para ver tus setups.")
                    self.actualizar_lista_circuitos()

    def seleccionar_carpeta(self):
        ruta_base = filedialog.askdirectory(title="Selecciona la raíz de Le Mans Ultimate")
        if ruta_base:
            ruta_final = ruta_base if "UserData" in ruta_base else os.path.join(ruta_base, "UserData", "player",
                                                                                "Settings")
            if not os.path.exists(ruta_final):
                self.log(f"⚠️ Atención: La carpeta {ruta_final} no existe en este directorio.")
                return
            self.ruta_destino = ruta_final
            texto_ruta = ".../" + "/".join(self.ruta_destino.replace("\\", "/").split("/")[-4:])
            self.label_ruta.configure(text=texto_ruta)
            self.label_info.configure(text="Carpeta cargada correctamente.\n\nPulsa 'Conectar al Bot' para empezar.",
                                      text_color="#2ecc71")
            with open(CONFIG_FILE, 'w') as f:
                json.dump({'ruta_setups': ruta_final}, f)
            self.log("Ruta configurada. Ve al Gestor para ver tus setups.")
            self.actualizar_lista_circuitos()

    # --- LÓGICA DEL GESTOR DE SETUPS Y CACHÉ DINÁMICA ---
    def actualizar_lista_circuitos(self):
        if not self.ruta_destino or not os.path.exists(self.ruta_destino): return

        meta_file = os.path.join(self.ruta_destino, "lmu_setups_db.json")
        self.meta_db = {}
        if os.path.exists(meta_file):
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    self.meta_db = json.load(f)
            except:
                pass

        self.setups_cache = []
        carpetas_brutas = [d for d in os.listdir(self.ruta_destino) if
                           os.path.isdir(os.path.join(self.ruta_destino, d))]
        carpetas = [d for d in carpetas_brutas if "sala de exposici" not in d.lower()]

        for c in carpetas:
            ruta_c = os.path.join(self.ruta_destino, c)
            archivos = [f for f in os.listdir(ruta_c) if
                        os.path.isfile(os.path.join(ruta_c, f)) and f.endswith(('.json', '.svm'))]

            for arch in archivos:
                meta = self.meta_db.get(arch, {})
                coche_bd = meta.get("coche")
                coche_norm = normalizar_coche_texto(coche_bd) if coche_bd else self.extraer_coche_fallback(arch)
                creador_norm = meta.get("creador") or extraer_creador_fallback(arch)

                self.setups_cache.append({
                    "archivo": arch,
                    "ruta": os.path.join(ruta_c, arch),
                    "circuito": c,
                    "coche": coche_norm,
                    "creador": creador_norm
                })

        if not hasattr(self, 'filtros_inicializados'):
            self.combo_circuitos.set("Todos los circuitos")
            self.combo_coches.set("Todos los coches")
            self.combo_creadores.set("Todos los creadores")
            self.filtros_inicializados = True

        self.aplicar_filtros_dinamicos()

    def aplicar_filtros_dinamicos(self, event=None):
        if not hasattr(self, 'setups_cache'): return

        sel_circ = self.combo_circuitos.get()
        sel_coche = self.combo_coches.get()
        sel_creador = self.combo_creadores.get()

        circuitos_validos = set()
        coches_validos = set()
        creadores_validos = set()
        archivos_a_mostrar = []

        for s in self.setups_cache:
            match_circ = (sel_circ == "Todos los circuitos" or s["circuito"] == sel_circ)
            match_coche = (sel_coche == "Todos los coches" or s["coche"] == sel_coche)
            match_creador = (sel_creador == "Todos los creadores" or s["creador"] == sel_creador)

            if match_coche and match_creador: circuitos_validos.add(s["circuito"])
            if match_circ and match_creador: coches_validos.add(s["coche"])
            if match_circ and match_coche: creadores_validos.add(s["creador"])

            if match_circ and match_coche and match_creador: archivos_a_mostrar.append(s)

        lista_circ = ["Todos los circuitos"] + sorted(list(circuitos_validos))
        lista_coches = ["Todos los coches"] + sorted(list(coches_validos))
        lista_creadores = ["Todos los creadores"] + sorted(list(creadores_validos))

        self.combo_circuitos.configure(values=lista_circ)
        self.combo_coches.configure(values=lista_coches)
        self.combo_creadores.configure(values=lista_creadores)

        if sel_circ not in lista_circ: self.combo_circuitos.set("Todos los circuitos")
        if sel_coche not in lista_coches: self.combo_coches.set("Todos los coches")
        if sel_creador not in lista_creadores: self.combo_creadores.set("Todos los creadores")

        for widget in self.frame_lista_setups.winfo_children(): widget.destroy()
        self.checkboxes_setups.clear()
        self.btn_seleccionar_todos.configure(text="☑️ Marcar")

        if not archivos_a_mostrar:
            ctk.CTkLabel(self.frame_lista_setups, text="No hay setups que coincidan con los filtros.",
                         text_color="gray").pack(pady=20)
            return

        archivos_a_mostrar.sort(key=lambda x: x["archivo"])
        for s in archivos_a_mostrar:
            texto_chk = f"[{s['circuito']}] {s['archivo']}" if self.combo_circuitos.get() == "Todos los circuitos" else \
            s["archivo"]
            chk = ctk.CTkCheckBox(self.frame_lista_setups, text=texto_chk, font=("Arial", 13))
            chk.pack(anchor="w", pady=6, padx=10)
            self.checkboxes_setups.append((chk, s["ruta"]))

    def toggle_seleccionar_todos(self):
        if not self.checkboxes_setups: return
        todos_marcados = all(chk.get() == 1 for chk, _ in self.checkboxes_setups)
        for chk, _ in self.checkboxes_setups: chk.deselect() if todos_marcados else chk.select()
        self.btn_seleccionar_todos.configure(text="☑️ Marcar" if todos_marcados else "🔳 Desmarcar")

    def eliminar_setups(self):
        eliminados = 0
        for chk, ruta_archivo in self.checkboxes_setups:
            if chk.get() == 1:
                try:
                    os.remove(ruta_archivo)
                    eliminados += 1
                except Exception as e:
                    self.log(f"Error borrando {os.path.basename(ruta_archivo)}: {e}")
        if eliminados > 0:
            self.log(f"🗑️ Se han eliminado {eliminados} setups.")
            self.actualizar_lista_circuitos()

    # --- FLUJO DE CONEXIÓN Y LOGIN ---
    def toggle_bot(self):
        if not self.ruta_destino:
            self.log("¡Error! Selecciona la carpeta LMU primero.")
            return
        self.tabview.set("📥 Descargas")
        if not self.bot_is_running:
            self.log("Conectando al servidor...")
            self.btn_iniciar.configure(state="disabled")
            asyncio.run_coroutine_threadsafe(self.conectar_telegram(), self.loop)
        else:
            self.log("Desconectando...")
            self.btn_iniciar.configure(state="disabled")
            asyncio.run_coroutine_threadsafe(self.desconectar_telegram(), self.loop)

    async def desconectar_telegram(self):
        if getattr(self, 'app_lo_silencio', False):
            try:
                await self.client(
                    UpdateNotifySettingsRequest(peer=BOT_USERNAME, settings=InputPeerNotifySettings(mute_until=0)))
            except Exception:
                pass
            self.app_lo_silencio = False
        await self.client.disconnect()
        self.after(0, self.restaurar_pantalla_inicio)

    async def conectar_telegram(self):
        await self.client.connect()
        if not await self.client.is_user_authorized():
            self.log("Se requiere iniciar sesión. Rellena los datos arriba.")
            self.after(0, self.mostrar_ui_telefono)
        else:
            await self.iniciar_escucha()

    def mostrar_ui_telefono(self):
        self.label_login.pack(pady=(10, 5))
        self.frame_login.pack(pady=5, padx=20, fill="x", after=self.frame_top)
        self.entry_phone.pack(pady=5)
        self.btn_phone.pack(pady=5)

    def pedir_codigo(self):
        telefono = self.entry_phone.get().strip()
        if not telefono: return
        self.btn_phone.configure(state="disabled")
        asyncio.run_coroutine_threadsafe(self.peticion_codigo_async(telefono), self.loop)

    async def peticion_codigo_async(self, telefono):
        try:
            await self.client.send_code_request(telefono)
            self.after(0, self.mostrar_ui_codigo)
        except Exception as e:
            self.log(f"Error: {e}")
            self.after(0, lambda: self.btn_phone.configure(state="normal"))

    def mostrar_ui_codigo(self):
        self.entry_phone.configure(state="disabled")
        self.entry_code.pack(pady=5)
        self.btn_code.pack(pady=5)

    def enviar_codigo(self):
        codigo = self.entry_code.get().strip()
        telefono = self.entry_phone.get().strip()
        if not codigo: return
        self.btn_code.configure(state="disabled")
        asyncio.run_coroutine_threadsafe(self.login_async(telefono, codigo), self.loop)

    async def login_async(self, telefono, codigo):
        try:
            await self.client.sign_in(telefono, codigo)
            self.after(0, self.frame_login.pack_forget)
            await self.iniciar_escucha()
        except Exception as e:
            self.log(f"Código incorrecto: {e}")
            self.after(0, lambda: self.btn_code.configure(state="normal"))

    async def iniciar_escucha(self):
        self.bot_is_running = True
        self.ultimo_texto_menu = None
        self.descarga_en_curso = False
        self.subcarpeta_circuito = ""
        self.after(0, lambda: self.btn_iniciar.configure(text="Desconectar", fg_color="red", state="normal"))
        await asyncio.sleep(2)

        try:
            try:
                peer = await self.client.get_input_entity(BOT_USERNAME)
                actual_settings = await self.client(GetNotifySettingsRequest(peer=InputNotifyPeer(peer=peer)))
                ya_silenciado = getattr(actual_settings, 'mute_until',
                                        None) and actual_settings.mute_until > datetime.datetime.now(
                    datetime.timezone.utc)
                if not ya_silenciado:
                    await self.client(UpdateNotifySettingsRequest(peer=BOT_USERNAME, settings=InputPeerNotifySettings(
                        mute_until=2147483647)))
                    self.app_lo_silencio = True
                else:
                    self.app_lo_silencio = False
            except Exception:
                pass

            await self.client.send_message(BOT_USERNAME, '/menu')
            await self.client.run_until_disconnected()
        except Exception:
            pass
        finally:
            self.bot_is_running = False
            self.log("Desconectado de forma segura.")
            self.after(0, self.restaurar_pantalla_inicio)

    # --- RENDERIZADO VISUAL DEL BOT Y LÓGICA INTELIGENTE ---
    def dibujar_interfaz_bot(self, texto_mensaje, botones_telegram):
        if getattr(self, 'descarga_en_curso', False): return

        texto_limpio = texto_mensaje.lower().replace("*", "")
        texto_sin_formato = texto_mensaje.replace("*", "")

        if "@" in texto_limpio:
            pista_raw = texto_limpio.split("@")[-1]
            carpeta_detectada = obtener_carpeta_circuito(pista_raw)
            if carpeta_detectada: self.subcarpeta_circuito = carpeta_detectada

        if "setups by" in texto_limpio and botones_telegram:
            creador_detectado = ""
            for c in ["HYMO2", "HYMO", "CDA", "P1Doks", "GO", "Bober"]:
                if f"setups by {c.lower()}" in texto_limpio: creador_detectado = c; break

            if creador_detectado and getattr(self, 'ultimo_texto_menu', None) != texto_limpio:
                self.ultimo_texto_menu = texto_limpio
                botones_a_descargar = []
                info_version = ""
                max_version = None

                carpeta_final_esperada = self.subcarpeta_circuito
                if carpeta_final_esperada:
                    ruta_guardado_esperada = os.path.join(self.ruta_destino, carpeta_final_esperada)
                    if not os.path.exists(ruta_guardado_esperada):
                        ModernDialog(self, "Carpeta no encontrada",
                                     f"La carpeta del circuito '{carpeta_final_esperada}' no existe en tu juego.\n\nGuarda un setup vacío en el juego primero.",
                                     is_warning=True).get_input()
                        self.ultimo_texto_menu = None
                        return

                if creador_detectado in ["HYMO", "HYMO2", "GO", "Bober", "P1Doks"]:
                    versiones = {}
                    for fila in botones_telegram:
                        for boton_tl in fila:
                            if "back" in boton_tl.text.lower() or "main menu" in boton_tl.text.lower(): continue
                            v_tuple = extraer_version_archivo(boton_tl.text, creador_detectado)
                            if v_tuple: versiones[boton_tl] = v_tuple

                    if versiones:
                        max_version = max(versiones.values())
                        botones_a_descargar = [btn for btn, v in versiones.items() if v == max_version]
                        str_max_version = ".".join(map(str, max_version)).replace(".0", "")
                        info_version = f" (v{str_max_version})"
                    else:
                        botones_a_descargar = [b for fila in botones_telegram for b in fila if
                                               "back" not in b.text.lower() and "main menu" not in b.text.lower()]
                        info_version = " (Todos)"
                else:
                    botones_a_descargar = [b for fila in botones_telegram for b in fila if
                                           "back" not in b.text.lower() and "main menu" not in b.text.lower()]
                    info_version = " (Todos)"

                m_coche = re.search(r'by\s+[^\-—]+\s*[-—]\s*(.+?)\s*@', texto_sin_formato, re.IGNORECASE)
                coche_menu = m_coche.group(1).strip() if m_coche else None

                archivos_antiguos = []
                archivos_actuales_exactos = []
                descarga_omitida = False
                nombres_botones_norm = [self.limpiar_texto(b.text) for b in botones_a_descargar]

                if self.subcarpeta_circuito:
                    ruta_circuito = os.path.join(self.ruta_destino, self.subcarpeta_circuito)
                    if os.path.exists(ruta_circuito):
                        archivos_circuito = [f for f in os.listdir(ruta_circuito) if f.endswith(('.json', '.svm'))]

                        for f in archivos_circuito:
                            if self.limpiar_texto(f.replace('.svm', '').replace('.json', '')) in nombres_botones_norm:
                                archivos_actuales_exactos.append(f)
                                continue

                            if max_version and coche_menu:
                                meta = self.meta_db.get(f, {})
                                c = normalizar_coche_texto(meta.get("coche") or self.extraer_coche_fallback(f))
                                cr = meta.get("creador") or extraer_creador_fallback(f)

                                if cr.lower() == creador_detectado.lower() and normalizar_coche_texto(
                                        coche_menu).lower() == c.lower():
                                    v_arch = extraer_version_archivo(f, creador_detectado)
                                    if v_arch and v_arch < max_version: archivos_antiguos.append(
                                        os.path.join(ruta_circuito, f))

                        if archivos_actuales_exactos:
                            res = ModernDialog(self, "Setups ya descargados",
                                               f"Ya tienes {len(archivos_actuales_exactos)} de estos setups en tu carpeta.\n\n¿Quieres omitir esta descarga para evitar duplicados?",
                                               is_warning=False).get_input()
                            if res:
                                self.log(f"Omitida la descarga de {creador_detectado}.")
                                descarga_omitida = True

                if descarga_omitida:
                    for widget in self.frame_bot_pantalla.winfo_children(): widget.destroy()
                    ctk.CTkLabel(self.frame_bot_pantalla,
                                 text=f"⏭️ Descarga Omitida\n\nYa tienes los setups de {creador_detectado}{info_version}\n\nCircuito: {self.subcarpeta_circuito or 'Settings'}",
                                 font=("Arial", 18, "bold"), text_color="#e67e22").pack(pady=(60, 20))
                    frame_nav = ctk.CTkFrame(self.frame_bot_pantalla, fg_color="transparent")
                    frame_nav.pack(pady=30)
                    for fila in botones_telegram:
                        for boton_tl in fila:
                            if "back" in boton_tl.text.lower() or "main menu" in boton_tl.text.lower():
                                def crear_comando(btn=boton_tl):
                                    async def click_seguro(): self.ultimo_texto_menu = None; await asyncio.sleep(
                                        1.0); await btn.click()

                                    return lambda: asyncio.run_coroutine_threadsafe(click_seguro(), self.loop)

                                ctk.CTkButton(frame_nav, text=boton_tl.text, command=crear_comando(), width=150,
                                              height=40, fg_color="#4a4a4a").pack(side="left", padx=10)
                    return

                if botones_a_descargar and archivos_antiguos:
                    if ModernDialog(self, "Setups antiguos detectados",
                                    f"Se han encontrado {len(archivos_antiguos)} setups antiguos de {creador_detectado}.\n\n¿Deseas eliminarlos antes de descargar la nueva versión {info_version.strip()}?",
                                    is_warning=True).get_input():
                        for arch in archivos_antiguos:
                            try:
                                os.remove(arch)
                            except:
                                pass
                        self.log(f"🗑️ Se han eliminado {len(archivos_antiguos)} setups antiguos.")
                        self.actualizar_lista_circuitos()

                if botones_a_descargar:
                    for widget in self.frame_bot_pantalla.winfo_children(): widget.destroy()
                    lbl_descargando = ctk.CTkLabel(self.frame_bot_pantalla,
                                                   text=f"📥 Descargando {len(botones_a_descargar)} setups de {creador_detectado}{info_version}\n\nCircuito: {self.subcarpeta_circuito or 'Settings'}",
                                                   font=("Arial", 18, "bold"), text_color="#3498db")
                    lbl_descargando.pack(pady=(60, 10))
                    self.progressbar = ctk.CTkProgressBar(self.frame_bot_pantalla, width=400, height=15)
                    self.progressbar.pack(pady=20)
                    self.progressbar.set(0)

                    frame_nav = ctk.CTkFrame(self.frame_bot_pantalla, fg_color="transparent")
                    frame_nav.pack(pady=30)
                    for fila in botones_telegram:
                        for boton_tl in fila:
                            if "back" in boton_tl.text.lower() or "main menu" in boton_tl.text.lower():
                                def crear_comando(btn=boton_tl):
                                    async def click_seguro():
                                        if getattr(self, 'descarga_en_curso', False): return
                                        self.ultimo_texto_menu = None;
                                        await asyncio.sleep(1.0);
                                        await btn.click()

                                    return lambda: asyncio.run_coroutine_threadsafe(click_seguro(), self.loop)

                                ctk.CTkButton(frame_nav, text=boton_tl.text, command=crear_comando(), width=150,
                                              height=40, fg_color="#4a4a4a").pack(side="left", padx=10)

                    self.log(f"Descarga masiva iniciada en /{self.subcarpeta_circuito or 'Settings'}.")

                    async def auto_descarga():
                        self.descarga_en_curso = True
                        try:
                            total = len(botones_a_descargar)
                            for i, btn in enumerate(botones_a_descargar, 1):
                                await btn.click();
                                await asyncio.sleep(3.5)
                                self.after(0, lambda v=i / total: self.progressbar.set(v))
                            self.log("✓ Lote completado con éxito.")
                            self.after(0, self.actualizar_lista_circuitos)
                            self.after(0, lambda: lbl_descargando.configure(
                                text=f"✅ ¡Descarga completada!\n\nSe han guardado {len(botones_a_descargar)} setups de {creador_detectado}{info_version}",
                                text_color="#2ecc71"))
                        finally:
                            self.descarga_en_curso = False

                    asyncio.run_coroutine_threadsafe(auto_descarga(), self.loop)

            if botones_a_descargar: return

        boton_get_setup = next(
            (b for fila in (botones_telegram or []) for b in fila if 'get a setup' in b.text.lower()), None)
        if boton_get_setup:
            async def auto_click_inicio(): await asyncio.sleep(1.5); await boton_get_setup.click()

            asyncio.run_coroutine_threadsafe(auto_click_inicio(), self.loop)
            return

        for widget in self.frame_bot_pantalla.winfo_children(): widget.destroy()
        if "setups by" not in texto_limpio: self.ultimo_texto_menu = None
        texto_mostrar = texto_mensaje.replace("**", "").replace("__", "").strip()

        match_step = re.search(r'(?i)step\s+(\d+)/(\d+)', texto_mostrar)
        if match_step:
            paso_actual, paso_total = int(match_step.group(1)), int(match_step.group(2))
            texto_mostrar = re.sub(r'(?i)step\s+\d+/\d+\.?\s*', '', texto_mostrar).strip()
            ctk.CTkLabel(self.frame_bot_pantalla, text=f"📍 Paso {paso_actual} de {paso_total}",
                         font=("Arial", 16, "bold"), text_color="#f39c12").pack(pady=(15, 5))
            prog_nav = ctk.CTkProgressBar(self.frame_bot_pantalla, width=250, height=8, progress_color="#f39c12")
            prog_nav.pack(pady=(0, 15))
            prog_nav.set(paso_actual / paso_total)

        if texto_mostrar:
            ctk.CTkLabel(self.frame_bot_pantalla, text=texto_mostrar, justify="center", wraplength=500,
                         font=("Arial", 15)).pack(pady=(5, 25))

        if botones_telegram:
            for fila in botones_telegram:
                frame_fila = ctk.CTkFrame(self.frame_bot_pantalla, fg_color="transparent")
                frame_fila.pack(pady=4)
                for boton_tl in fila:
                    es_nav = "back" in boton_tl.text.lower() or "main menu" in boton_tl.text.lower()

                    def crear_comando(btn=boton_tl, is_nav=es_nav):
                        async def click_seguro():
                            if getattr(self, 'descarga_en_curso', False): return
                            if is_nav: self.ultimo_texto_menu = None
                            await asyncio.sleep(1.5);
                            await btn.click()

                        return lambda: asyncio.run_coroutine_threadsafe(click_seguro(), self.loop)

                    btn_color, btn_hover = ("#4a4a4a", "#333333") if es_nav else ("#1f538d", "#14375e")
                    ctk.CTkButton(frame_fila, text=boton_tl.text, command=crear_comando(), width=220, height=40,
                                  fg_color=btn_color, hover_color=btn_hover, font=("Arial", 13, "bold")).pack(
                        side="left", padx=6)

    # --- EVENTOS DE TELEGRAM ---
    async def handler_mensajes(self, event):
        mensaje = event.message
        if mensaje.media and hasattr(mensaje, 'file') and mensaje.file:
            nombre = mensaje.file.name or "setup_desconocido.json"
            texto_archivo = mensaje.text or ""

            meta_coche = (re.search(r'🏎️\s*([^\n]+)', texto_archivo) or type('obj', (object,),
                                                                             {'group': lambda self, x: None})()).group(
                1)
            meta_circuito = (re.search(r'📍\s*([^\n]+)', texto_archivo) or type('obj', (object,), {
                'group': lambda self, x: None})()).group(1)
            meta_creador = (re.search(r'👨‍🔧\s*([^\n]+)', texto_archivo) or type('obj', (object,), {
                'group': lambda self, x: None})()).group(1)
            meta_carpeta = (re.search(r'Settings\\([^\\]+)\\', texto_archivo) or type('obj', (object,), {
                'group': lambda self, x: None})()).group(1)

            coche_limpio_bd = normalizar_coche_texto(meta_coche) if meta_coche else normalizar_coche_texto(nombre)
            carpeta_final = meta_carpeta.strip() if meta_carpeta else self.subcarpeta_circuito

            ruta_guardado = os.path.join(self.ruta_destino, carpeta_final) if carpeta_final else self.ruta_destino
            if carpeta_final and not os.path.exists(ruta_guardado): return

            await event.download_media(file=os.path.join(ruta_guardado, nombre))

            if meta_coche or meta_creador:
                meta_file = os.path.join(self.ruta_destino, "lmu_setups_db.json")
                db = {}
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, 'r', encoding='utf-8') as f:
                            db = json.load(f)
                    except:
                        pass

                db[nombre] = {
                    "coche": coche_limpio_bd,
                    "circuito": meta_circuito.strip() if meta_circuito else carpeta_final,
                    "creador": meta_creador.strip() if meta_creador else extraer_creador_fallback(nombre)
                }
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(db, f, indent=4)

            if not getattr(self, 'descarga_en_curso', False):
                self.log(f"✓ {nombre} guardado en /{carpeta_final or 'Settings'}.")
                self.after(0, self.actualizar_lista_circuitos)
            return

        self.after(0, lambda txt=mensaje.text or "[Mensaje sin texto]",
                             btns=getattr(mensaje, 'buttons', None): self.dibujar_interfaz_bot(txt, btns))


if __name__ == "__main__":
    app = LMUApp()
    app.mainloop()