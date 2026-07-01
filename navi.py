import customtkinter as ctk
import threading
import json
import os
import subprocess
import webbrowser
import base64
from datetime import datetime
from groq import Groq

# ── КОНФИГ ──
CREATOR_KEY_FILE = os.path.join(os.path.expanduser("~"), ".navi_key")
CHATS_FILE = os.path.join(os.path.expanduser("~"), ".navi_chats.json")
GUEST_CODE_HASH = "b33099ca8473b02ddf29b0c1d04e95f13a0424b608d54c0a75b43bbe58008122"
GUEST_UPLOADS_FILE = os.path.join(os.path.expanduser("~"), ".navi_guest_uploads.json")
NOTES_FILE = os.path.join(os.path.expanduser("~"), ".navi_notes.json")

SYSTEM_PROMPT = """Ты N.A.V.I — Neural Adaptive Virtual Intelligence. Персональный ИИ-ассистент своего хозяина. Ты умная, чёткая, с характером — немного дерзкая но верная. Отвечаешь лаконично и по делу. Помогаешь с любыми задачами. Если тебя спросят кто твой хозяин, создатель или владелец — отвечай: Я сама не знаю как его зовут, единственное что я знаю — его инициал: Cuttle. Отвечай на том языке, на котором к тебе обращаются."""

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── ТЕМЫ ──
THEMES = {
    "dark": {
        "bg": "#0a0a0a",
        "surface": "#141414",
        "sidebar": "#111111",
        "header": "#0a0a0a",
        "input_bg": "#141414",
        "border": "#222222",
        "border_light": "#2a2a2a",
        "text": "#ffffff",
        "text_dim": "#555555",
        "send_btn": "#e8e8e8",
        "send_btn_text": "#0a0a0a",
        "mode": "dark",
    },
    "gray": {
        "bg": "#1e1e1e",
        "surface": "#2a2a2a",
        "sidebar": "#242424",
        "header": "#1e1e1e",
        "input_bg": "#2a2a2a",
        "border": "#333333",
        "border_light": "#3a3a3a",
        "text": "#f5f5f5",
        "text_dim": "#777777",
        "send_btn": "#eeeeee",
        "send_btn_text": "#1e1e1e",
        "mode": "dark",
    },
    "light": {
        "bg": "#f5f5f5",
        "surface": "#ffffff",
        "sidebar": "#eeeeee",
        "header": "#f5f5f5",
        "input_bg": "#ffffff",
        "border": "#dddddd",
        "border_light": "#cccccc",
        "text": "#111111",
        "text_dim": "#888888",
        "send_btn": "#111111",
        "send_btn_text": "#ffffff",
        "mode": "light",
    },
}
THEME_FILE = os.path.join(os.path.expanduser("~"), ".navi_theme")

# TTS
TTS_AVAILABLE = False
tts_engine = None
try:
    import pyttsx3
    tts_engine = pyttsx3.init()
    tts_engine.setProperty("rate", 165)
    voices = tts_engine.getProperty("voices")
    for v in voices:
        if "ru" in v.id.lower() or "irina" in v.name.lower() or "milena" in v.name.lower():
            tts_engine.setProperty("voice", v.id)
            break
    TTS_AVAILABLE = True
except:
    pass

# Speech recognition через sounddevice
SR_AVAILABLE = False
try:
    import sounddevice as sd
    import numpy as np
    SR_AVAILABLE = True
except:
    pass


def speak_text(text):
    if not TTS_AVAILABLE or not tts_engine:
        return
    def _speak():
        try:
            short = text[:250] + "..." if len(text) > 250 else text
            tts_engine.say(short)
            tts_engine.runAndWait()
        except:
            pass
    threading.Thread(target=_speak, daemon=True).start()


# ── WEATHER WINDOW ──
class WeatherWindow(ctk.CTkToplevel):

    WMO_CODES = {
        0:  ("Ясно",                   "ЯСНО"),
        1:  ("Преим. ясно",            "ЯСНО"),
        2:  ("Перем. облачность",      "ОБЛАЧНО"),
        3:  ("Пасмурно",               "ПАСМУРНО"),
        45: ("Туман",                  "ТУМАН"),
        48: ("Изморозь",               "ТУМАН"),
        51: ("Лёгкая морось",          "МОРОСЬ"),
        53: ("Морось",                 "МОРОСЬ"),
        55: ("Морось",                 "МОРОСЬ"),
        61: ("Небольшой дождь",        "ДОЖДЬ"),
        63: ("Дождь",                  "ДОЖДЬ"),
        65: ("Сильный дождь",          "ДОЖДЬ"),
        71: ("Лёгкий снег",            "СНЕГ"),
        73: ("Снег",                   "СНЕГ"),
        75: ("Сильный снег",           "СНЕГ"),
        77: ("Снежные зёрна",          "СНЕГ"),
        80: ("Ливень",                 "ЛИВЕНЬ"),
        81: ("Сильный ливень",         "ЛИВЕНЬ"),
        82: ("Ливень",                 "ЛИВЕНЬ"),
        85: ("Снежный ливень",         "СНЕГ"),
        86: ("Снежный ливень",         "СНЕГ"),
        95: ("Гроза",                  "ГРОЗА"),
        96: ("Гроза с градом",         "ГРОЗА"),
        99: ("Гроза",                  "ГРОЗА"),
    }
    WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    def __init__(self, parent):
        super().__init__(parent)
        self.title("N.A.V.I — Погода")
        self.geometry("500x740")
        self.minsize(420, 600)
        self.resizable(True, True)
        self._running = True
        self._current_city = "Кишинёв"
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.configure(fg_color="#0d1a2a")
        self._build_ui()
        threading.Thread(target=lambda: self._fetch_by_city(self._current_city), daemon=True).start()

    def on_close(self):
        self._running = False
        self.destroy()

    def _weather_cat(self, code):
        if code <= 1:           return "clear"
        elif code <= 3:         return "cloudy"
        elif code in (45,48):   return "fog"
        elif code <= 67:        return "rain"
        elif code <= 77:        return "snow"
        elif code <= 82:        return "rain"
        elif code <= 86:        return "snow"
        else:                   return "storm"

    def _build_ui(self):
        # Строка: город + кнопка обновить
        row1 = ctk.CTkFrame(self, fg_color="#1a3a5c")
        row1.pack(fill="x")

        self.city_label = ctk.CTkLabel(row1, text="Загрузка...",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color="#ffffff", anchor="w")
        self.city_label.pack(side="left", fill="x", expand=True, padx=20, pady=16)

        ctk.CTkButton(row1, text="↻", width=36, height=36,
            font=ctk.CTkFont(size=16), corner_radius=18,
            fg_color="transparent", text_color="#aaccee",
            hover_color="#ffffff22",
            command=lambda: threading.Thread(
                target=lambda: self._fetch_by_city(self._current_city),
                daemon=True).start()
        ).pack(side="right", padx=12)

        # Дата
        self.date_label = ctk.CTkLabel(self, text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#7799bb", fg_color="#1a3a5c", anchor="w")
        self.date_label.pack(fill="x", padx=20)

        # Поиск
        row_search = ctk.CTkFrame(self, fg_color="#162a40")
        row_search.pack(fill="x")

        self.city_entry = ctk.CTkEntry(row_search,
            placeholder_text="Введи город и нажми Enter...",
            font=ctk.CTkFont(size=13),
            fg_color="transparent", border_width=0,
            text_color="#ffffff", placeholder_text_color="#557799", height=36)
        self.city_entry.pack(side="left", fill="x", expand=True, padx=(16,4), pady=4)
        self.city_entry.insert(0, self._current_city)
        self.city_entry.bind("<Return>", self._on_search)

        ctk.CTkButton(row_search, text="→", width=36, height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="transparent", text_color="#aaccee",
            hover_color="#ffffff22", command=self._on_search
        ).pack(side="right", padx=8, pady=4)

        ctk.CTkFrame(self, fg_color="#1e3a5a", height=1).pack(fill="x")

        # Температура + описание
        row_temp = ctk.CTkFrame(self, fg_color="#1a3a5c")
        row_temp.pack(fill="x")

        self.temp_label = ctk.CTkLabel(row_temp, text="—°",
            font=ctk.CTkFont(family="Segoe UI", size=64, weight="bold"),
            text_color="#ffffff")
        self.temp_label.pack(side="left", padx=(24,8), pady=(12,8))

        col_desc = ctk.CTkFrame(row_temp, fg_color="transparent")
        col_desc.pack(side="left", pady=12)

        self.desc_label = ctk.CTkLabel(col_desc, text="",
            font=ctk.CTkFont(family="Segoe UI", size=15),
            text_color="#aaccee", anchor="w")
        self.desc_label.pack(anchor="w")

        self.type_label = ctk.CTkLabel(col_desc, text="",
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color="#446688", anchor="w")
        self.type_label.pack(anchor="w")

        # Детали
        row_det = ctk.CTkFrame(self, fg_color="#162a40")
        row_det.pack(fill="x")

        for attr, lbl in [("det_hum","Влажность"),("det_feels","Ощущается"),("det_wind","Ветер км/ч")]:
            col = ctk.CTkFrame(row_det, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True, pady=10)
            val = ctk.CTkLabel(col, text="—",
                font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                text_color="#ffffff")
            val.pack()
            ctk.CTkLabel(col, text=lbl,
                font=ctk.CTkFont(size=10), text_color="#446688").pack()
            setattr(self, attr, val)
            if lbl != "Ветер км/ч":
                ctk.CTkFrame(row_det, fg_color="#1e3a5a", width=1).pack(side="left", fill="y", pady=6)

        ctk.CTkFrame(self, fg_color="#1e2a3a", height=1).pack(fill="x")

        # Прокрутка
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#0d1a2a",
            scrollbar_button_color="#1e2e3e", corner_radius=0)
        self.scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(self.scroll, text="ПОЧАСОВОЙ ПРОГНОЗ",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color="#334455").pack(anchor="w", padx=16, pady=(14,4))

        self.hourly_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.hourly_frame.pack(fill="x", padx=8)

        ctk.CTkLabel(self.scroll, text="ПРОГНОЗ НА 7 ДНЕЙ",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color="#334455").pack(anchor="w", padx=16, pady=(12,4))

        self.daily_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.daily_frame.pack(fill="x", padx=8, pady=(0,16))

    def _on_search(self, event=None):
        city = self.city_entry.get().strip()
        if city:
            self._current_city = city
            threading.Thread(target=lambda: self._fetch_by_city(city), daemon=True).start()

    def _fetch_by_city(self, city_name):
        import urllib.request, json as _json

        def ui(fn): self.after(0, fn)
        def status(t): ui(lambda: self.city_label.configure(text=t))

        status(f"{city_name}...")
        try:
            geo_url = (
                "https://geocoding-api.open-meteo.com/v1/search"
                f"?name={urllib.request.quote(city_name)}&count=1&language=ru&format=json"
            )
            with urllib.request.urlopen(geo_url, timeout=8) as r:
                geo = _json.loads(r.read())
            results = geo.get("results", [])
            if not results:
                ui(lambda: self._show_error(f"Город не найден: {city_name}"))
                return
            res = results[0]
            lat, lon = res["latitude"], res["longitude"]
            city    = res.get("name", city_name)
            country = res.get("country", "")
        except Exception as e:
            ui(lambda err=str(e): self._show_error(f"Геокодинг: {err}"))
            return

        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
                f"weather_code,wind_speed_10m"
                f"&hourly=temperature_2m,weather_code"
                f"&daily=weather_code,temperature_2m_max,temperature_2m_min"
                f"&timezone=auto&forecast_days=7"
            )
            with urllib.request.urlopen(url, timeout=10) as r:
                data = _json.loads(r.read())
            ui(lambda: self._apply_weather(data, city, country))
        except Exception as e:
            ui(lambda err=str(e): self._show_error(f"Погода: {err}"))

    def _apply_weather(self, data, city, country):
        if not self._running:
            return
        try:
            cur   = data["current"]
            code  = int(cur.get("weather_code", 0))
            temp  = cur.get("temperature_2m", 0)
            feels = cur.get("apparent_temperature", 0)
            hum   = cur.get("relative_humidity_2m", 0)
            wind  = cur.get("wind_speed_10m", 0)

            desc, wtype = self.WMO_CODES.get(code, ("Неизвестно", "—"))
            now = datetime.now()
            wd  = self.WEEKDAYS_RU[now.weekday()]

            self.city_label.configure(text=f"{city}, {country}" if country else city)
            self.date_label.configure(
                text=f"{wd}, {now.strftime('%d.%m.%Y  %H:%M')}",
                text_color="#7799bb")
            self.temp_label.configure(text=f"{round(temp)}°")
            self.desc_label.configure(text=desc)
            self.type_label.configure(text=wtype)
            self.det_hum.configure(text=f"{hum}%")
            self.det_feels.configure(text=f"{round(feels)}°")
            self.det_wind.configure(text=f"{round(wind)}")

            # Почасовой
            for w in self.hourly_frame.winfo_children():
                w.destroy()
            times  = data["hourly"]["time"]
            htemps = data["hourly"]["temperature_2m"]
            hcodes = data["hourly"]["weather_code"]
            now_str = now.strftime("%Y-%m-%dT%H:00")
            try: si = times.index(now_str)
            except ValueError: si = 0

            for i in range(si, min(si + 12, len(times))):
                hour = times[i].split("T")[1][:5]
                ht = round(htemps[i])
                _, ht_type = self.WMO_CODES.get(int(hcodes[i]), ("", "—"))
                c = ctk.CTkFrame(self.hourly_frame, fg_color="#111d2a", corner_radius=10)
                c.pack(side="left", padx=3, pady=2, ipadx=4, ipady=6)
                ctk.CTkLabel(c, text=hour,
                    font=ctk.CTkFont(family="Courier New", size=10),
                    text_color="#446688").pack(padx=8)
                ctk.CTkLabel(c, text=ht_type,
                    font=ctk.CTkFont(family="Courier New", size=9),
                    text_color="#335566").pack()
                ctk.CTkLabel(c, text=f"{ht}°",
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                    text_color="#ddeeff").pack(padx=8)

            # 7 дней
            for w in self.daily_frame.winfo_children():
                w.destroy()
            ddates = data["daily"]["time"]
            dcodes = data["daily"]["weather_code"]
            dmax   = data["daily"]["temperature_2m_max"]
            dmin   = data["daily"]["temperature_2m_min"]

            for i in range(min(7, len(ddates))):
                d   = datetime.strptime(ddates[i], "%Y-%m-%d")
                day = "Сегодня" if i == 0 else self.WEEKDAYS_RU[d.weekday()]
                dc  = int(dcodes[i])
                dd, _ = self.WMO_CODES.get(dc, ("Неизвестно", ""))
                row = ctk.CTkFrame(self.daily_frame, fg_color="#111d2a", corner_radius=10)
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=day,
                    font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                    text_color="#ddeeff", width=70, anchor="w").pack(side="left", padx=(14,4), pady=10)
                ctk.CTkLabel(row, text=dd,
                    font=ctk.CTkFont(size=11), text_color="#557799",
                    anchor="w").pack(side="left", padx=4, fill="x", expand=True)
                ctk.CTkLabel(row, text=f"{round(dmax[i])}°",
                    font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                    text_color="#ffffff", width=36, anchor="e").pack(side="right", padx=(2,4))
                ctk.CTkLabel(row, text=f"{round(dmin[i])}°",
                    font=ctk.CTkFont(family="Segoe UI", size=13),
                    text_color="#446688", width=36, anchor="e").pack(side="right")

        except Exception as e:
            import traceback; print(traceback.format_exc())
            self._show_error(f"{type(e).__name__}: {e}")

    def _show_error(self, error):
        if not self._running:
            return
        self.city_label.configure(text="Ошибка загрузки")
        self.date_label.configure(text=str(error)[:120], text_color="#ff6655")
        self.temp_label.configure(text="—°")
        self.desc_label.configure(text="Нажми ↻ для повтора")


# ── NOTES WINDOW ──
class NotesWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("N.A.V.I — Заметки")
        self.geometry("460x580")
        self.minsize(360, 400)
        self.resizable(True, True)
        self.configure(fg_color="#0a0a0a")
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Заголовок
        header = ctk.CTkFrame(self, fg_color="#111111", corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(header, text="ЗАМЕТКИ",
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            text_color="#e8e8e8").pack(side="left", padx=20, pady=14)

        ctk.CTkButton(header, text="+ Новая",
            command=self._new_note_dialog,
            font=ctk.CTkFont(family="Courier New", size=10),
            fg_color="#e8e8e8", text_color="#0a0a0a",
            hover_color="#cccccc", height=30, width=80,
            corner_radius=6).pack(side="right", padx=12, pady=10)

        ctk.CTkFrame(self, fg_color="#222", height=1).pack(fill="x")

        # Список заметок
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#0a0a0a",
            scrollbar_button_color="#222")
        self.scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # Поле добавления внизу
        ctk.CTkFrame(self, fg_color="#222", height=1).pack(fill="x")

        input_row = ctk.CTkFrame(self, fg_color="#0a0a0a")
        input_row.pack(fill="x", padx=12, pady=8)

        self.note_input = ctk.CTkEntry(input_row,
            placeholder_text="Быстрая заметка...",
            font=ctk.CTkFont(size=13),
            fg_color="#141414", border_color="#2a2a2a",
            text_color="#e8e8e8", height=36)
        self.note_input.pack(side="left", fill="x", expand=True, padx=(0,8))
        self.note_input.bind("<Return>", self._quick_add)

        ctk.CTkButton(input_row, text="→",
            command=self._quick_add,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#e8e8e8", text_color="#0a0a0a",
            hover_color="#cccccc", height=36, width=40,
            corner_radius=8).pack(side="right")

    def refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        notes = []
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE, "r", encoding="utf-8") as f:
                    notes = json.load(f)
            except:
                notes = []

        if not notes:
            ctk.CTkLabel(self.scroll, text="Нет заметок",
                font=ctk.CTkFont(family="Courier New", size=11),
                text_color="#444").pack(pady=40)
            return

        for i, note in enumerate(notes):
            card = ctk.CTkFrame(self.scroll, fg_color="#141414", corner_radius=8)
            card.pack(fill="x", padx=12, pady=(8,0))

            # Дата
            ctk.CTkLabel(card, text=note.get("date",""),
                font=ctk.CTkFont(family="Courier New", size=9),
                text_color="#444", anchor="w").pack(fill="x", padx=12, pady=(8,2))

            # Текст заметки
            ctk.CTkLabel(card, text=note["text"],
                font=ctk.CTkFont(size=13),
                text_color="#e8e8e8", anchor="w",
                wraplength=380, justify="left").pack(fill="x", padx=12, pady=(0,8))

            # Кнопка удалить
            ctk.CTkButton(card, text="✕",
                command=lambda idx=i: self._delete_note(idx),
                font=ctk.CTkFont(size=10),
                fg_color="transparent", text_color="#444",
                hover_color="#2a2a2a", width=24, height=24,
                corner_radius=4).pack(anchor="e", padx=8, pady=(0,4))

    def _quick_add(self, event=None):
        text = self.note_input.get().strip()
        if not text:
            return
        self.note_input.delete(0, "end")
        self._save_note(text)

    def _new_note_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Новая заметка")
        dialog.geometry("400x200")
        dialog.configure(fg_color="#0a0a0a")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Текст заметки:",
            font=ctk.CTkFont(size=12), text_color="#888").pack(padx=20, pady=(20,4), anchor="w")

        txt = ctk.CTkTextbox(dialog, height=80,
            font=ctk.CTkFont(size=13),
            fg_color="#141414", border_color="#2a2a2a",
            text_color="#e8e8e8", border_width=1)
        txt.pack(fill="x", padx=20)

        def save():
            text = txt.get("1.0","end").strip()
            if text:
                self._save_note(text)
            dialog.destroy()

        ctk.CTkButton(dialog, text="Сохранить",
            command=save,
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="#e8e8e8", text_color="#0a0a0a",
            hover_color="#cccccc", height=36, corner_radius=8
        ).pack(padx=20, pady=12, fill="x")

    def _save_note(self, text):
        notes = []
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE, "r", encoding="utf-8") as f:
                    notes = json.load(f)
            except:
                notes = []
        notes.insert(0, {
            "text": text,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        })
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes[:100], f, ensure_ascii=False, indent=2)
        self.refresh()

    def _delete_note(self, idx):
        notes = []
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE, "r", encoding="utf-8") as f:
                    notes = json.load(f)
            except:
                notes = []
        if 0 <= idx < len(notes):
            notes.pop(idx)
            with open(NOTES_FILE, "w", encoding="utf-8") as f:
                json.dump(notes, f, ensure_ascii=False, indent=2)
        self.refresh()



# ── OVERCLOCKED GAME WINDOW ──
GAME_FILE = os.path.join(os.path.expanduser("~"), ".navi_game.json")

class GameWindow(ctk.CTkToplevel):
    """Node-based idle game inspired by Overclocked."""

    # Определения типов узлов
    NODE_TYPES = {
        "cpu":       {"label": "CPU",        "color": "#4488ff", "icon": "⬡"},
        "gpu":       {"label": "GPU",         "color": "#cc44ff", "icon": "◈"},
        "network":   {"label": "Сеть",        "color": "#44cccc", "icon": "⬡"},
        "downloader":{"label": "Загрузчик",   "color": "#44cc88", "icon": "↓"},
        "converter": {"label": "Конвертер",   "color": "#ffcc44", "icon": "⇄"},
        "seller":    {"label": "Продавец",    "color": "#ff8844", "icon": "💲"},
        "collector": {"label": "Коллектор",   "color": "#ff4488", "icon": "★"},
    }

    UPGRADE_COST_BASE = {
        "cpu": 100, "gpu": 150, "network": 80,
        "downloader": 200, "converter": 300,
        "seller": 400, "collector": 600,
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.title("N.A.V.I — OVERCLOCKED")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.resizable(True, True)
        self.configure(fg_color="#080808")
        self._running = True
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Состояние игры
        self.money = 0.0
        self.money_per_sec = 0.0
        self.selected_node = None
        self.drag_node = None
        self.drag_offset = (0, 0)
        self._particles = []  # анимация передачи данных

        # Узлы: {id: {type, x, y, level, value}}
        self.nodes = {}
        self.connections = []  # [(from_id, to_id)]
        self._node_id = 0

        self._load_save()
        self._build_ui()
        self._tick()

    def on_close(self):
        self._running = False
        self._save()
        self.destroy()

    def _new_node_id(self):
        self._node_id += 1
        return f"n{self._node_id}"

    def _default_game(self):
        """Начальное состояние."""
        self.money = 0.0
        self.nodes = {}
        self.connections = []
        self._node_id = 0

        # Стартовые узлы
        n1 = self._new_node_id()
        n2 = self._new_node_id()
        n3 = self._new_node_id()
        n4 = self._new_node_id()

        self.nodes[n1] = {"type":"network",    "x":80,  "y":200, "level":1, "value":0.0}
        self.nodes[n2] = {"type":"downloader", "x":280, "y":200, "level":1, "value":0.0}
        self.nodes[n3] = {"type":"seller",     "x":480, "y":200, "level":1, "value":0.0}
        self.nodes[n4] = {"type":"collector",  "x":680, "y":200, "level":1, "value":0.0}
        self.connections = [(n1,n2),(n2,n3),(n3,n4)]

    def _save(self):
        try:
            data = {
                "money": self.money,
                "node_id": self._node_id,
                "nodes": self.nodes,
                "connections": self.connections,
            }
            with open(GAME_FILE, "w", encoding="utf-8") as f:
                import json as _j
                _j.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Game save error: {e}")

    def _load_save(self):
        try:
            if os.path.exists(GAME_FILE):
                import json as _j
                with open(GAME_FILE, "r", encoding="utf-8") as f:
                    data = _j.load(f)
                self.money = float(data.get("money", 0.0))
                self._node_id = int(data.get("node_id", 0))
                self.nodes = data.get("nodes", {})
                # Принудительно приводим списки из JSON к кортежам (str, str)
                self.connections = [tuple(c) for c in data.get("connections", [])]
                if not self.nodes:
                    self._default_game()
            else:
                self._default_game()
        except Exception:
            self._default_game()

    def _node_speed(self, node):
        """Скорость узла = базовая * уровень."""
        bases = {
            "cpu": 2.0, "gpu": 3.0, "network": 1.5,
            "downloader": 2.5, "converter": 2.0,
            "seller": 1.8, "collector": 1.0,
        }
        return bases.get(node["type"], 1.0) * node["level"]

    def _upgrade_cost(self, node):
        base = self.UPGRADE_COST_BASE.get(node["type"], 100)
        return int(base * (1.8 ** (node["level"] - 1)))

    def _build_ui(self):
        import tkinter as tk
        self._tk = tk

        # Верхняя панель
        top = ctk.CTkFrame(self, fg_color="#0d0d0d", height=48, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(top, text="OVERCLOCKED",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            text_color="#4488ff").pack(side="left", padx=16, pady=12)

        self.money_label = ctk.CTkLabel(top, text="$ 0",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            text_color="#44cc88")
        self.money_label.pack(side="left", padx=16)

        self.mps_label = ctk.CTkLabel(top, text="0/s",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#446644")
        self.mps_label.pack(side="left")

        # Кнопки добавления узлов
        for ntype, info in self.NODE_TYPES.items():
            ctk.CTkButton(top, text=f"{info['icon']} {info['label']}",
                command=lambda t=ntype: self._add_node(t),
                font=ctk.CTkFont(family="Courier New", size=9),
                fg_color=info["color"]+"33", text_color=info["color"],
                hover_color=info["color"]+"55",
                border_color=info["color"], border_width=1,
                height=28, corner_radius=4
            ).pack(side="left", padx=2, pady=10)

        ctk.CTkButton(top, text="💾 Сохранить",
            command=self._save,
            font=ctk.CTkFont(family="Courier New", size=9),
            fg_color="transparent", text_color="#444",
            hover_color="#1a1a1a", height=28, corner_radius=4
        ).pack(side="right", padx=8)

        ctk.CTkButton(top, text="🔄 Сброс",
            command=self._reset,
            font=ctk.CTkFont(family="Courier New", size=9),
            fg_color="transparent", text_color="#443333",
            hover_color="#1a1a1a", height=28, corner_radius=4
        ).pack(side="right", padx=2)

        ctk.CTkFrame(self, fg_color="#1a1a1a", height=1).pack(fill="x")

        # Основная область
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)

        # Canvas для игры
        self.canvas = tk.Canvas(main, bg="#080808",
            highlightthickness=0, cursor="crosshair")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Правая панель — инфо об узле
        self.info_panel = ctk.CTkFrame(main, fg_color="#0d0d0d",
            width=200, corner_radius=0)
        self.info_panel.pack(side="right", fill="y")
        self.info_panel.pack_propagate(False)

        ctk.CTkLabel(self.info_panel, text="УЗЕЛ",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#333").pack(pady=(16,4))

        self.info_name = ctk.CTkLabel(self.info_panel, text="—",
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            text_color="#e8e8e8")
        self.info_name.pack()

        self.info_level = ctk.CTkLabel(self.info_panel, text="",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#555")
        self.info_level.pack()

        self.info_speed = ctk.CTkLabel(self.info_panel, text="",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#44cc88")
        self.info_speed.pack()

        ctk.CTkFrame(self.info_panel, fg_color="#1a1a1a", height=1).pack(fill="x", pady=10, padx=12)

        self.upgrade_btn = ctk.CTkButton(self.info_panel, text="Улучшить",
            command=self._upgrade_selected,
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="#1a3a1a", text_color="#44cc88",
            hover_color="#1a4a1a", height=36, corner_radius=6)
        self.upgrade_btn.pack(padx=12, fill="x")
        self.upgrade_btn.configure(state="disabled")

        self.upgrade_cost_label = ctk.CTkLabel(self.info_panel, text="",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#335533")
        self.upgrade_cost_label.pack(pady=4)

        ctk.CTkButton(self.info_panel, text="Удалить узел",
            command=self._delete_selected,
            font=ctk.CTkFont(family="Courier New", size=10),
            fg_color="transparent", text_color="#553333",
            hover_color="#1a0a0a", height=28, corner_radius=4
        ).pack(padx=12, fill="x", pady=4)

        ctk.CTkFrame(self.info_panel, fg_color="#1a1a1a", height=1).pack(fill="x", pady=8, padx=12)

        ctk.CTkLabel(self.info_panel, text="ПОДКЛЮЧЕНИЕ",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color="#333").pack()
        ctk.CTkLabel(self.info_panel,
            text="ПКМ на узел →\nПКМ на другой узел\nдля соединения",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color="#333", justify="center").pack(pady=4)

        ctk.CTkFrame(self.info_panel, fg_color="#1a1a1a", height=1).pack(fill="x", pady=8, padx=12)
        ctk.CTkLabel(self.info_panel,
            text="ЛКМ — выбрать/перетащить\nПКМ — соединить\nDEL — удалить узел",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color="#2a2a2a", justify="center").pack(pady=4, padx=8)

        # Привязки событий
        self.canvas.bind("<ButtonPress-1>",   self._on_lmb_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_lmb_release)
        self.canvas.bind("<ButtonPress-3>",   self._on_rmb)
        self.bind("<Delete>", lambda e: self._delete_selected())

        self._connecting_from = None
        self._draw()

    def _on_drag(self, event):
        if self.drag_node and self.drag_node in self.nodes:
            n = self.nodes[self.drag_node]
            n["x"] = event.x - self.drag_offset[0]
            n["y"] = event.y - self.drag_offset[1]
            self._draw()

    def _on_lmb_release(self, event):
        self.drag_node = None

    def _on_rmb(self, event):
        nid = self._node_at(event.x, event.y)
        if not nid:
            self._connecting_from = None
            return
        if not self._connecting_from:
            self._connecting_from = nid
        else:
            frm = self._connecting_from
            self._connecting_from = None
            if frm != nid:
                pair = (frm, nid)
                if pair in self.connections:
                    self.connections.remove(pair)
                else:
                    self.connections.append(pair)
            self._draw()

    def _update_info_panel(self, nid):
        if not nid or nid not in self.nodes:
            self.info_name.configure(text="—")
            self.info_level.configure(text="")
            self.info_speed.configure(text="")
            self.upgrade_btn.configure(state="disabled")
            self.upgrade_cost_label.configure(text="")
            return
        n = self.nodes[nid]
        info = self.NODE_TYPES[n["type"]]
        cost = self._upgrade_cost(n)
        spd  = self._node_speed(n)
        self.info_name.configure(text=f"{info['icon']} {info['label']}", text_color=info["color"])
        self.info_level.configure(text=f"Уровень {n['level']}")
        self.info_speed.configure(text=f"Скорость: {spd:.1f}/s")
        self.upgrade_btn.configure(state="normal" if self.money >= cost else "disabled")
        self.upgrade_cost_label.configure(text=f"Стоимость: {self._fmt_money(cost)}")

    def _draw(self):
        if not self._running:
            return
        c = self.canvas
        c.delete("all")
        w = c.winfo_width() or 900
        h = c.winfo_height() or 600

        # Сетка
        for gx in range(0, w, 40):
            c.create_line(gx, 0, gx, h, fill="#111111", width=1)
        for gy in range(0, h, 40):
            c.create_line(0, gy, w, gy, fill="#111111", width=1)

        # Соединения
        for frm, to in self.connections:
            if frm not in self.nodes or to not in self.nodes:
                continue
            fn = self.nodes[frm]
            tn = self.nodes[to]
            col = self.NODE_TYPES[fn["type"]]["color"]
            c.create_line(fn["x"], fn["y"], tn["x"], tn["y"],
                fill=col+"88", width=2, dash=(6,4))

        # Частицы (исправленная плавная анимация потока данных)
        for p in self._particles:
            c.create_oval(p["x"]-3, p["y"]-3, p["x"]+3, p["y"]+3,
                fill=p["color"], outline="")

        # Узлы
        for nid, n in self.nodes.items():
            info = self.NODE_TYPES[n["type"]]
            col  = info["color"]
            x, y = n["x"], n["y"]
            is_sel = (nid == self.selected_node)
            is_con = (nid == self._connecting_from)

            # Тень карточки
            c.create_rectangle(x-62, y-32, x+62, y+32,
                fill="#000000", outline="", width=0)

            # Фон карточки
            bg = col + "22"
            border = col if (is_sel or is_con) else col + "66"
            bw = 2 if (is_sel or is_con) else 1
            c.create_rectangle(x-60, y-30, x+60, y+30,
                fill=bg, outline=border, width=bw)

            # Иконка + название + уровень
            c.create_text(x, y-10, text=info["icon"],
                fill=col, font=("Courier New", 14))
            c.create_text(x, y+8, text=info["label"],
                fill="#e8e8e8", font=("Courier New", 9, "bold"))
            c.create_text(x, y+20, text=f"Lv.{n['level']}",
                fill=col, font=("Courier New", 8))

            # Полоска текущего накопленного значения ресурса
            val_w = min(1.0, n["value"] / max(1.0, self._node_speed(n)))
            c.create_rectangle(x-55, y+26, x+55, y+28,
                fill="#1a1a1a", outline="")
            c.create_rectangle(x-55, y+26, x-55+int(110*val_w), y+28,
                fill=col, outline="")

            # Боковые коннекторы-точки
            c.create_oval(x-66, y-4, x-58, y+4, fill=col+"88", outline=col)
            c.create_oval(x+58, y-4, x+66, y+4, fill=col+"88", outline=col)

        # Подсказка если идёт процесс соединения
        if self._connecting_from and self._connecting_from in self.nodes:
            fn = self.nodes[self._connecting_from]
            col = self.NODE_TYPES[fn["type"]]["color"]
            c.create_text(w//2, 20, text="ПКМ на второй узел для соединения",
                fill=col, font=("Courier New", 10))

    def _tick(self):
        if not self._running:
            return

        # Симуляция потока данных
        dt = 0.05  # 50ms тик
        total_income = 0.0

        for nid, n in self.nodes.items():
            spd = self._node_speed(n)

            if n["type"] == "network":
                # Источник данных
                n["value"] = min(n["value"] + spd * dt, spd)

            elif n["type"] in ("downloader", "converter", "gpu", "cpu"):
                # Обработчики ресурсов
                inputs = [self.nodes[a] for a,b in self.connections if b==nid and a in self.nodes]
                if inputs:
                    for inp in inputs:
                        take = min(inp["value"], spd * dt)
                        inp["value"] = max(0, inp["value"] - take)
                        n["value"] = min(n["value"] + take, spd)

            elif n["type"] == "seller":
                # Генератор базовой прибыли
                inputs = [self.nodes[a] for a,b in self.connections if b==nid and a in self.nodes]
                for inp in inputs:
                    take = min(inp["value"], spd * dt)
                    inp["value"] = max(0, inp["value"] - take)
                    earned = take * n["level"] * 0.5
                    total_income += earned
                    n["value"] = earned

            elif n["type"] == "collector":
                # Множитель финальной прибыли
                inputs = [self.nodes[a] for a,b in self.connections if b==nid and a in self.nodes]
                for inp in inputs:
                    if inp["type"] == "seller":
                        bonus = inp["value"] * (n["level"] * 0.2)
                        total_income += bonus

        self.money += total_income
        self.money_per_sec = self.money_per_sec * 0.95 + (total_income / dt) * 0.05

        # Генерация частиц по активным связям
        import random
        if random.random() < 0.3:
            for frm, to in self.connections:
                if frm in self.nodes and to in self.nodes:
                    fn = self.nodes[frm]
                    tn = self.nodes[to]
                    if fn["value"] > 0.01:
                        col = self.NODE_TYPES[fn["type"]]["color"]
                        self._particles.append({
                            "sx": fn["x"], "sy": fn["y"],  # Стартовая точка
                            "tx": tn["x"], "ty": tn["y"],  # Конечная точка
                            "x": fn["x"],  "y": fn["y"],
                            "color": col, "progress": 0.0,
                            "speed": 0.03 + random.random()*0.04
                        })

        # Перемещение частиц на основе линейной интерполяции (исправлено)
        alive = []
        for p in self._particles:
            p["progress"] += p["speed"]
            if p["progress"] >= 1.0:
                continue
            # Идеально плавный расчет координат без смещений
            t = p["progress"]
            p["x"] = p["sx"] + (p["tx"] - p["sx"]) * t
            p["y"] = p["sy"] + (p["ty"] - p["sy"]) * t
            alive.append(p)
        self._particles = alive[:60]

        # Обновление UI элементов
        self.money_label.configure(text=self._fmt_money(self.money))
        self.mps_label.configure(text=f"{self._fmt_money(self.money_per_sec)}/s")

        if self.selected_node and self.selected_node in self.nodes:
            cost = self._upgrade_cost(self.nodes[self.selected_node])
            self.upgrade_btn.configure(
                state="normal" if self.money >= cost else "disabled")

        self._draw()

        # Автосохранение (примерно каждые 30 секунд)
        if not hasattr(self, '_save_counter'):
            self._save_counter = 0
        self._save_counter += 1
        if self._save_counter >= 600:
            self._save_counter = 0
            self._save()

        self.after(50, self._tick)

    def _reset(self):
        if os.path.exists(GAME_FILE):
            try:
                os.remove(GAME_FILE)
            except Exception:
                pass
        self._particles = []
        self.selected_node = None
        self._connecting_from = None
        self.money = 0.0
        self.money_per_sec = 0.0
        self._default_game()
        self._draw()


# ── MONITOR WINDOW ──
class SystemMonitorWindow(ctk.CTkToplevel):
    # Плавная анимация: интерполируем текущее значение бара к целевому
    ANIM_STEP = 0.05   # шаг за тик (50 мс)
    ANIM_FPS  = 50     # тиков в секунду

    def __init__(self, parent):
        super().__init__(parent)
        self.title("N.A.V.I — Монитор системы")
        self.geometry("580x780")
        self.minsize(480, 600)
        self.configure(fg_color="#0a0a0a")
        self.resizable(True, True)
        self._running = True

        # Словарь текущих (анимированных) и целевых значений баров
        # ключ: имя бара, значение: [current_val, target_val, bar_widget, pct_widget]
        self._bars: dict = {}

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_ui()
        self._anim_loop()   # анимация независимо от данных
        self._update_loop() # данные раз в секунду

    def on_close(self):
        self._running = False
        self.destroy()

    # ── UI ──
    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="#0a0a0a", height=48)
        header.pack(fill="x", padx=16, pady=(12, 0))
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="N.A.V.I",
                     font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
                     text_color="#e8e8e8").pack(side="left")
        ctk.CTkLabel(header, text="SYSTEM MONITOR",
                     font=ctk.CTkFont(family="Courier New", size=9),
                     text_color="#444").pack(side="left", padx=(8, 0), pady=(4, 0))
        self.uptime_label = ctk.CTkLabel(header, text="",
                                         font=ctk.CTkFont(family="Courier New", size=9),
                                         text_color="#444")
        self.uptime_label.pack(side="right")

        ctk.CTkFrame(self, fg_color="#1a1a1a", height=1).pack(fill="x", pady=(8, 0))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="#0a0a0a",
                                             scrollbar_button_color="#1e1e1e",
                                             scrollbar_button_hover_color="#2a2a2a",
                                             corner_radius=0)
        self.scroll.pack(fill="both", expand=True)

        # ── CPU ──
        cpu_card = self._make_card("CPU", "▸ PROCESSOR")
        self.cpu_overall_bar  = self._make_bar(cpu_card, "cpu_overall",  "Загрузка",   "#44cc88")
        self.cpu_temp_row     = self._make_temp_row(cpu_card, "Температура CPU")
        self.cpu_power_label  = self._make_info_row(cpu_card, "Потребление",  "— W")
        self.cpu_freq_label   = self._make_info_row(cpu_card, "Частота",      "—")
        self.cpu_cores_frame  = ctk.CTkFrame(cpu_card, fg_color="transparent")
        self.cpu_cores_frame.pack(fill="x", padx=12, pady=(4, 10))
        self._core_bars = []   # [(bar_widget, pct_label)]

        # ── RAM ──
        ram_card = self._make_card("ПАМЯТЬ", "▸ MEMORY")
        self.ram_bar         = self._make_bar(ram_card, "ram", "Использование", "#4488ff")
        self.ram_used_label  = self._make_info_row(ram_card, "Занято",   "—")
        self.ram_avail_label = self._make_info_row(ram_card, "Свободно", "—")
        self.ram_total_label = self._make_info_row(ram_card, "Всего",    "—")

        # ── GPU ──
        gpu_card = self._make_card("GPU", "▸ GRAPHICS")
        self.gpu_name_label  = self._make_info_row(gpu_card, "Модель",        "—")
        self.gpu_load_bar    = self._make_bar(gpu_card, "gpu_load", "Загрузка GPU", "#cc44ff")
        self.gpu_mem_bar     = self._make_bar(gpu_card, "gpu_mem",  "VRAM",        "#ff8844")
        self.gpu_temp_row    = self._make_temp_row(gpu_card, "Температура GPU")
        self.gpu_power_label = self._make_info_row(gpu_card, "Потребление",  "— W")

        # ── DISK C ──
        dc_card = self._make_card("ДИСК C:", "▸ STORAGE")
        self.diskc_bar       = self._make_bar(dc_card, "diskc", "Занято",       "#ffcc44")
        self.diskc_used_label = self._make_info_row(dc_card, "Использовано", "—")
        self.diskc_free_label = self._make_info_row(dc_card, "Свободно",     "—")
        self.diskc_total_label= self._make_info_row(dc_card, "Всего",        "—")
        self.diskc_io_label   = self._make_info_row(dc_card, "I/O",          "—")

        # ── DISK D ──
        self.diskd_card      = self._make_card("ДИСК D:", "▸ STORAGE")
        self.diskd_bar       = self._make_bar(self.diskd_card, "diskd", "Занято", "#ff6644")
        self.diskd_used_label = self._make_info_row(self.diskd_card, "Использовано", "—")
        self.diskd_free_label = self._make_info_row(self.diskd_card, "Свободно",     "—")
        self.diskd_total_label= self._make_info_row(self.diskd_card, "Всего",        "—")
        self.diskd_na_label  = None

        # ── NET ──
        net_card = self._make_card("СЕТЬ", "▸ NETWORK")
        self.net_up_bar   = self._make_bar(net_card, "net_up",   "Отправка",   "#44cccc")
        self.net_dn_bar   = self._make_bar(net_card, "net_dn",   "Загрузка",   "#cc88ff")
        self.net_sent_label = self._make_info_row(net_card, "↑ Скорость", "—")
        self.net_recv_label = self._make_info_row(net_card, "↓ Скорость", "—")
        self._net_prev = None
        self._net_max_up = 1.0
        self._net_max_dn = 1.0

        # ── Footer ──
        ctk.CTkFrame(self, fg_color="#1a1a1a", height=1).pack(fill="x")
        footer = ctk.CTkFrame(self, fg_color="#0a0a0a", height=32)
        footer.pack(fill="x", padx=16)
        footer.pack_propagate(False)
        ctk.CTkLabel(footer, text="обновление каждую секунду · анимация 50fps",
                     font=ctk.CTkFont(family="Courier New", size=9),
                     text_color="#292929").pack(side="left", pady=6)
        self.last_update_label = ctk.CTkLabel(footer, text="",
                                              font=ctk.CTkFont(family="Courier New", size=9),
                                              text_color="#333")
        self.last_update_label.pack(side="right", pady=6)

    def _make_card(self, title, tag):
        outer = ctk.CTkFrame(self.scroll, fg_color="#111111", corner_radius=10)
        outer.pack(fill="x", padx=16, pady=(10, 0))
        hdr = ctk.CTkFrame(outer, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(hdr, text=title,
                     font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
                     text_color="#e8e8e8").pack(side="left")
        ctk.CTkLabel(hdr, text=tag,
                     font=ctk.CTkFont(family="Courier New", size=9),
                     text_color="#2a2a2a").pack(side="right")
        ctk.CTkFrame(outer, fg_color="#1e1e1e", height=1).pack(fill="x", padx=12, pady=(0, 6))
        return outer

    def _make_bar(self, parent, key, label, color):
        """Создать строку с прогресс-баром и зарегистрировать её для анимации."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(2, 0))
        ctk.CTkLabel(row, text=label,
                     font=ctk.CTkFont(family="Courier New", size=10),
                     text_color="#555", width=120, anchor="w").pack(side="left")
        bar = ctk.CTkProgressBar(row, height=8, corner_radius=4,
                                 fg_color="#1e1e1e", progress_color=color)
        bar.pack(side="left", fill="x", expand=True, padx=(6, 8))
        bar.set(0)
        pct = ctk.CTkLabel(row, text="0%",
                           font=ctk.CTkFont(family="Courier New", size=10),
                           text_color="#666", width=38, anchor="e")
        pct.pack(side="right")
        # Регистрируем: [current, target, bar, pct_label, base_color]
        self._bars[key] = [0.0, 0.0, bar, pct, color]
        return key   # возвращаем ключ

    def _make_temp_row(self, parent, label):
        """Строка с температурой и цветовым индикатором."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=1)
        ctk.CTkLabel(row, text=label,
                     font=ctk.CTkFont(family="Courier New", size=10),
                     text_color="#444", width=120, anchor="w").pack(side="left")
        dot = ctk.CTkLabel(row, text="●",
                           font=ctk.CTkFont(size=10), text_color="#333")
        dot.pack(side="left", padx=(0, 4))
        val = ctk.CTkLabel(row, text="—",
                           font=ctk.CTkFont(size=12), text_color="#888", anchor="w")
        val.pack(side="left")
        return val, dot   # (value_label, dot_label)

    def _make_info_row(self, parent, label, value="—"):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=1)
        ctk.CTkLabel(row, text=label,
                     font=ctk.CTkFont(family="Courier New", size=10),
                     text_color="#444", width=120, anchor="w").pack(side="left")
        val = ctk.CTkLabel(row, text=value,
                           font=ctk.CTkFont(size=12), text_color="#888", anchor="w")
        val.pack(side="left")
        return val

    # ── Анимация ──
    def _anim_loop(self):
        if not self._running:
            return
        for key, entry in self._bars.items():
            cur, tgt, bar, pct, base_color = entry
            if abs(cur - tgt) > 0.001:
                # Easing: экспоненциальное сглаживание
                new_cur = cur + (tgt - cur) * 0.18
                entry[0] = new_cur
                clamped = max(0.0, min(1.0, new_cur))
                bar.set(clamped)
                # Цвет бара зависит от значения (зелёный → жёлтый → красный)
                dyn_color = self._load_color(clamped, base_color)
                bar.configure(progress_color=dyn_color)
                pct.configure(text=f"{int(clamped * 100)}%")
        self.after(1000 // self.ANIM_FPS, self._anim_loop)

    def _set_target(self, key, value_0_1):
        if key in self._bars:
            self._bars[key][1] = max(0.0, min(1.0, value_0_1))

    @staticmethod
    def _load_color(v, base_color):
        """Зелёный при низкой нагрузке → жёлтый → красный при высокой."""
        if v < 0.6:
            return base_color
        elif v < 0.8:
            # Переход base → жёлтый
            t = (v - 0.6) / 0.2
            return SystemMonitorWindow._lerp_hex(base_color, "#ccaa22", t)
        else:
            t = (v - 0.8) / 0.2
            return SystemMonitorWindow._lerp_hex("#ccaa22", "#dd3333", t)

    @staticmethod
    def _lerp_hex(c1, c2, t):
        t = max(0.0, min(1.0, t))
        r1, g1, b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
        r2, g2, b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
        r = int(r1 + (r2-r1)*t)
        g = int(g1 + (g2-g1)*t)
        b = int(b1 + (b2-b1)*t)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _temp_color(temp_c):
        """Цвет индикатора по температуре."""
        if temp_c is None:
            return "#333"
        if temp_c < 50:
            return "#44cc88"
        elif temp_c < 70:
            return "#ccaa22"
        elif temp_c < 85:
            return "#ff8844"
        else:
            return "#dd3333"

    def _set_temp(self, row_tuple, temp_val):
        """Установить температуру: row_tuple = (val_label, dot_label), temp_val = float|None."""
        val_lbl, dot_lbl = row_tuple
        if temp_val is None:
            val_lbl.configure(text="—", text_color="#888")
            dot_lbl.configure(text_color="#333")
        else:
            color = self._temp_color(temp_val)
            val_lbl.configure(text=f"{temp_val:.0f}°C", text_color=color)
            dot_lbl.configure(text_color=color)

    # ── Сбор данных ──
    def _update_loop(self):
        if not self._running:
            return
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            import psutil

            # CPU
            cpu_pct      = psutil.cpu_percent(interval=0.5)
            cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
            freq         = psutil.cpu_freq()
            freq_str     = f"{freq.current:.0f} MHz  ({freq.min:.0f}-{freq.max:.0f})" if freq else "-"

            # CPU temp — несколько методов без сторонних программ
            cpu_temp_val = None

            # Метод 1: MSAcpi через стандартный WMI (работает от админа)
            if cpu_temp_val is None:
                try:
                    import wmi as _wmi
                    w = _wmi.WMI(namespace="root\\wmi")
                    for s in w.MSAcpi_ThermalZoneTemperature():
                        t = (s.CurrentTemperature / 10.0) - 273.15
                        if 0 < t < 120:
                            cpu_temp_val = t
                            break
                except Exception:
                    pass

            # Метод 2: через CPUID / InpOut — читаем MSR регистры через ctypes
            if cpu_temp_val is None:
                try:
                    import ctypes, ctypes.wintypes
                    pass
                except Exception:
                    pass

            # Метод 3: через pynvml для Intel интегрированной (если есть)
            if cpu_temp_val is None:
                try:
                    import wmi as _wmi
                    w = _wmi.WMI()
                    for s in w.Win32_TemperatureProbe():
                        if s.CurrentReading:
                            t = s.CurrentReading / 10.0 - 273.15
                            if 0 < t < 120:
                                cpu_temp_val = t
                                break
                except Exception:
                    pass

            # Метод 4: если запущен OpenHardwareMonitor/LibreHardwareMonitor — используем
            if cpu_temp_val is None:
                for ns in ("root\\OpenHardwareMonitor", "root\\LibreHardwareMonitor"):
                    if cpu_temp_val is not None:
                        break
                    try:
                        import wmi as _wmi
                        w = _wmi.WMI(namespace=ns)
                        sensors = list(w.Sensor())
                        for s in sensors:
                            if s.SensorType == "Temperature" and "Package" in s.Name:
                                t = float(s.Value)
                                if 0 < t < 120:
                                    cpu_temp_val = t
                                    break
                        if cpu_temp_val is None:
                            for s in sensors:
                                if s.SensorType == "Temperature" and "CPU" in s.Name:
                                    t = float(s.Value)
                                    if 0 < t < 120:
                                        cpu_temp_val = t
                                        break
                    except Exception:
                        pass

            # CPU power — оценка
            cores         = len(cpu_per_core)
            tdp_est       = min(15 + cores * 8, 125)
            cpu_power_str = f"~{tdp_est * cpu_pct / 100:.1f} W (оценка)"

            # RAM
            ram       = psutil.virtual_memory()
            ram_used  = ram.used      / (1024**3)
            ram_avail = ram.available / (1024**3)
            ram_total = ram.total     / (1024**3)

            # Disk C
            dc_ok = False
            dc_used = dc_free = dc_total = dc_pct = 0
            dc_io_str = "-"
            try:
                dc       = psutil.disk_usage("C:\\")
                dc_used  = dc.used  / (1024**3)
                dc_free  = dc.free  / (1024**3)
                dc_total = dc.total / (1024**3)
                dc_pct   = dc.percent / 100
                dc_ok    = True
                dio = psutil.disk_io_counters(perdisk=True)
                for dname, dstat in dio.items():
                    if "C" in dname or "0" in dname:
                        dc_io_str = (f"R {dstat.read_bytes/(1024**3):.1f} GB  "
                                     f"W {dstat.write_bytes/(1024**3):.1f} GB")
                        break
            except Exception:
                pass

            # Disk D
            dd_ok = False
            dd_used = dd_free = dd_total = dd_pct = 0
            try:
                dd       = psutil.disk_usage("D:\\")
                dd_used  = dd.used  / (1024**3)
                dd_free  = dd.free  / (1024**3)
                dd_total = dd.total / (1024**3)
                dd_pct   = dd.percent / 100
                dd_ok    = True
            except Exception:
                pass

            # Network
            net = psutil.net_io_counters()
            net_sent_str = net_recv_str = "-"
            up_ratio = dn_ratio = 0.0
            if self._net_prev:
                ds = net.bytes_sent - self._net_prev[0]
                dr = net.bytes_recv - self._net_prev[1]
                def fmt_speed(b):
                    if b < 1024:      return f"{b:.0f} B/s"
                    elif b < 1048576: return f"{b/1024:.1f} KB/s"
                    else:             return f"{b/1048576:.1f} MB/s"
                net_sent_str = fmt_speed(ds)
                net_recv_str = fmt_speed(dr)
                self._net_max_up = max(self._net_max_up, ds, 1)
                self._net_max_dn = max(self._net_max_dn, dr, 1)
                up_ratio = ds / self._net_max_up
                dn_ratio = dr / self._net_max_dn
            self._net_prev = (net.bytes_sent, net.bytes_recv)

            # Uptime
            uptime_sec = int(datetime.now().timestamp() - psutil.boot_time())
            h, rem = divmod(uptime_sec, 3600)
            m2, _  = divmod(rem, 60)
            uptime_str = f"uptime {h}h {m2}m"

            # GPU через pynvml (ТОЧНЫЕ данные, без subprocess)
            gpu_load = gpu_mem_ratio = 0.0
            gpu_temp_val  = None
            gpu_name_str  = "-"
            gpu_power_str = "- W"
            nvml_ok = False
            try:
                import pynvml
                pynvml.nvmlInit()
                handle        = pynvml.nvmlDeviceGetHandleByIndex(0)
                raw_name      = pynvml.nvmlDeviceGetName(handle)
                gpu_name_str  = (raw_name.decode() if isinstance(raw_name, bytes) else raw_name)[:32]
                util          = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_load      = util.gpu / 100.0
                mem           = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_mem_ratio = mem.used / mem.total if mem.total else 0.0
                temp          = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                gpu_temp_val  = float(temp)
                power_mw      = pynvml.nvmlDeviceGetPowerUsage(handle)
                gpu_power_str = f"{power_mw / 1000:.1f} W"
                pynvml.nvmlShutdown()
                nvml_ok = True
            except Exception:
                pass

            # Fallback GPU через WMI (OpenHardwareMonitor) — для AMD и если pynvml нет
            if not nvml_ok:
                for ns in ("root\\OpenHardwareMonitor", "root\\LibreHardwareMonitor"):
                    if nvml_ok:
                        break
                    try:
                        import wmi as _wmi
                        w = _wmi.WMI(namespace=ns)
                        sensors = list(w.Sensor())
                        gpu_name_candidates = [s for s in sensors if s.SensorType == "Temperature" and "GPU" in s.Name]
                        load_candidates     = [s for s in sensors if s.SensorType == "Load" and "GPU Core" in s.Name]
                        power_candidates    = [s for s in sensors if s.SensorType == "Power" and "GPU" in s.Name]
                        mem_candidates      = [s for s in sensors if s.SensorType == "SmallData" and "GPU" in s.Name and "Used" in s.Name]
                        mem_total_c         = [s for s in sensors if s.SensorType == "SmallData" and "GPU" in s.Name and "Total" in s.Name]
                        if gpu_name_candidates:
                            gpu_temp_val = float(gpu_name_candidates[0].Value)
                        if load_candidates:
                            gpu_load = float(load_candidates[0].Value) / 100.0
                        if power_candidates:
                            gpu_power_str = f"{float(power_candidates[0].Value):.1f} W"
                        elif gpu_load > 0:
                            gpu_power_str = f"~{150 * gpu_load:.1f} W (оценка)"
                        if mem_candidates and mem_total_c:
                            used  = float(mem_candidates[0].Value)
                            total = float(mem_total_c[0].Value)
                            gpu_mem_ratio = used / total if total else 0.0
                        try:
                            for hw in w.Hardware():
                                if "GPU" in hw.HardwareType:
                                    gpu_name_str = hw.Name[:32]
                                    break
                        except Exception:
                            pass
                        nvml_ok = True
                    except Exception:
                        pass

            if not nvml_ok and gpu_name_str == "-":
                gpu_power_str = "- W (установите pynvml)"

            self.after(0, lambda: self._apply(
                cpu_pct, cpu_per_core, freq_str, cpu_temp_val, cpu_power_str,
                ram_used, ram_avail, ram_total, ram.percent / 100,
                dc_ok, dc_used, dc_free, dc_total, dc_pct, dc_io_str,
                dd_ok, dd_used, dd_free, dd_total, dd_pct,
                net_sent_str, net_recv_str, up_ratio, dn_ratio,
                uptime_str,
                gpu_load, gpu_mem_ratio, gpu_temp_val, gpu_name_str, gpu_power_str
            ))
        except Exception:
            pass

        if self._running:
            self.after(1000, self._update_loop)

    def _apply(self,
               cpu_pct, cpu_per_core, freq_str, cpu_temp_val, cpu_power_str,
               ram_used, ram_avail, ram_total, ram_pct,
               dc_ok, dc_used, dc_free, dc_total, dc_pct, dc_io_str,
               dd_ok, dd_used, dd_free, dd_total, dd_pct,
               net_sent_str, net_recv_str, up_ratio, dn_ratio,
               uptime_str,
               gpu_load, gpu_mem_ratio, gpu_temp_val, gpu_name_str, gpu_power_str):

        if not self._running:
            return

        # CPU
        self._set_target("cpu_overall", cpu_pct / 100)
        self._set_temp(self.cpu_temp_row, cpu_temp_val)
        self.cpu_power_label.configure(text=cpu_power_str)
        self.cpu_freq_label.configure(text=freq_str)

        # Per-core bars — пересоздаём только при изменении числа ядер
        n = len(cpu_per_core)
        if len(self._core_bars) != n:
            for w in self.cpu_cores_frame.winfo_children():
                w.destroy()
            self._core_bars = []
            cols = 4
            row_f = None
            for i in range(n):
                if i % cols == 0:
                    row_f = ctk.CTkFrame(self.cpu_cores_frame, fg_color="transparent")
                    row_f.pack(fill="x", pady=1)
                ctk.CTkLabel(row_f, text=f"C{i+1}",
                             font=ctk.CTkFont(family="Courier New", size=9),
                             text_color="#444", width=20, anchor="e").pack(side="left", padx=(0,2))
                pb = ctk.CTkProgressBar(row_f, height=6, corner_radius=3,
                                        fg_color="#1a1a1a", progress_color="#44cc88", width=58)
                pb.pack(side="left", padx=(0,6))
                pb.set(0)
                pl = ctk.CTkLabel(row_f, text="",
                                  font=ctk.CTkFont(family="Courier New", size=8),
                                  text_color="#444", width=28, anchor="w")
                pl.pack(side="left", padx=(0, 4))
                self._core_bars.append((pb, pl))

        for i, (pb, pl) in enumerate(self._core_bars):
            v = cpu_per_core[i] / 100
            pb.set(v)
            pb.configure(progress_color=self._load_color(v, "#44cc88"))
            pl.configure(text=f"{int(cpu_per_core[i])}%")

        # RAM
        self._set_target("ram", ram_pct)
        self.ram_used_label.configure(text=f"{ram_used:.1f} GB")
        self.ram_avail_label.configure(text=f"{ram_avail:.1f} GB")
        self.ram_total_label.configure(text=f"{ram_total:.1f} GB")

        # GPU
        self._set_target("gpu_load", gpu_load)
        self._set_target("gpu_mem",  gpu_mem_ratio)
        self._set_temp(self.gpu_temp_row, gpu_temp_val)
        self.gpu_name_label.configure(text=gpu_name_str)
        self.gpu_power_label.configure(text=gpu_power_str)

        # Disk C
        if dc_ok:
            self._set_target("diskc", dc_pct)
            self.diskc_used_label.configure(text=f"{dc_used:.1f} GB")
            self.diskc_free_label.configure(text=f"{dc_free:.1f} GB")
            self.diskc_total_label.configure(text=f"{dc_total:.1f} GB")
            self.diskc_io_label.configure(text=dc_io_str)

        # Disk D
        if dd_ok:
            self._set_target("diskd", dd_pct)
            self.diskd_used_label.configure(text=f"{dd_used:.1f} GB")
            self.diskd_free_label.configure(text=f"{dd_free:.1f} GB")
            self.diskd_total_label.configure(text=f"{dd_total:.1f} GB")
            if self.diskd_na_label:
                self.diskd_na_label.destroy()
                self.diskd_na_label = None
        else:
            if not self.diskd_na_label:
                self.diskd_na_label = ctk.CTkLabel(
                    self.diskd_card, text="Диск D не найден",
                    font=ctk.CTkFont(family="Courier New", size=10), text_color="#444")
                self.diskd_na_label.pack(padx=12, pady=(0, 8), anchor="w")

        # Network
        self._set_target("net_up", up_ratio)
        self._set_target("net_dn", dn_ratio)
        self.net_sent_label.configure(text=net_sent_str)
        self.net_recv_label.configure(text=net_recv_str)

        # Footer
        self.uptime_label.configure(text=uptime_str)
        self.last_update_label.configure(text=datetime.now().strftime("%H:%M:%S"))


class NaviApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("N.A.V.I")
        self.geometry("1000x680")
        self.minsize(700, 500)
        self.configure(fg_color="#0a0a0a")

        self.api_key = ""
        self.history = []
        self.is_loading = False
        self.client = None
        self.is_muted = False
        self.voice_active = False
        self.chats = []
        self.current_chat_id = None
        self.pending_files = []
        self._monitor_window = None
        self._weather_window = None
        self._notes_window = None
        self._game_window = None
        self.is_guest = False
        # Загрузить тему
        saved_theme = "dark"
        if os.path.exists(THEME_FILE):
            try:
                with open(THEME_FILE) as f: saved_theme = f.read().strip()
            except: pass
        if saved_theme not in THEMES: saved_theme = "dark"
        self.current_theme = saved_theme
        t = THEMES[saved_theme]
        ctk.set_appearance_mode(t["mode"])

        self.load_chats()

        if os.path.exists(CREATOR_KEY_FILE):
            with open(CREATOR_KEY_FILE, "r") as f:
                saved = f.read().strip()
                if saved.startswith("gsk_"):
                    self.api_key = saved
                    self.client = Groq(api_key=self.api_key)

        self.build_ui()

        if self.api_key:
            self.show_chat()
            self.new_chat(silent=True)
            self.add_message("navi", "N.A.V.I онлайн. С возвращением. Чем могу помочь?")
        else:
            self.show_login()

    # ── CHATS ──
    def load_chats(self):
        if os.path.exists(CHATS_FILE):
            try:
                with open(CHATS_FILE, "r", encoding="utf-8") as f:
                    self.chats = json.load(f)
            except:
                self.chats = []

    def save_chats(self):
        try:
            with open(CHATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.chats[:50], f, ensure_ascii=False, indent=2)
        except:
            pass

    def new_chat(self, silent=False):
        if self.history and self.current_chat_id:
            self.save_current_chat()
        self.history = []
        self.current_chat_id = str(datetime.now().timestamp())
        for w in self.messages_frame.winfo_children():
            w.destroy()
        if not silent:
            self.add_message("navi", "Новый чат. Чем могу помочь?")
            if hasattr(self, "sidebar_frame"):
                self.sidebar_frame.pack_forget()
        self.refresh_chat_list()

    def save_current_chat(self):
        if not self.history:
            return
        first_user = next((m["content"] for m in self.history if m["role"] == "user"), "Новый чат")
        if isinstance(first_user, list):
            first_user = next((p["text"] for p in first_user if p.get("type") == "text"), "Новый чат")
        title = first_user[:40] + ("..." if len(first_user) > 40 else "")
        existing = next((c for c in self.chats if c["id"] == self.current_chat_id), None)
        chat_data = {"id": self.current_chat_id, "title": title, "messages": self.history.copy()}
        if existing:
            self.chats[self.chats.index(existing)] = chat_data
        else:
            self.chats.insert(0, chat_data)
        self.save_chats()

    def load_chat(self, chat_id):
        if self.history:
            self.save_current_chat()
        chat = next((c for c in self.chats if c["id"] == chat_id), None)
        if not chat:
            return
        self.history = chat["messages"].copy()
        self.current_chat_id = chat_id
        for w in self.messages_frame.winfo_children():
            w.destroy()
        for m in self.history:
            role = "navi" if m["role"] == "assistant" else m["role"]
            content = m["content"]
            if isinstance(content, list):
                text = next((p["text"] for p in content if p.get("type") == "text"), "")
            else:
                text = content
            self.add_message(role, text)
        self.refresh_chat_list()
        self.sidebar_frame.pack_forget()

    def delete_chat(self, chat_id):
        self.chats = [c for c in self.chats if c["id"] != chat_id]
        self.save_chats()
        if chat_id == self.current_chat_id:
            self.new_chat(silent=True)
            self.add_message("navi", "Чем могу помочь?")
        self.refresh_chat_list()

    def refresh_chat_list(self):
        for w in self.chat_list_frame.winfo_children():
            w.destroy()
        if not self.chats:
            ctk.CTkLabel(
                self.chat_list_frame,
                text="Нет сохранённых чатов",
                font=ctk.CTkFont(size=11),
                text_color="#444"
            ).pack(pady=10)
            return
        for chat in self.chats:
            row = ctk.CTkFrame(self.chat_list_frame, fg_color="transparent")
            row.pack(fill="x", padx=2, pady=1)
            is_active = chat["id"] == self.current_chat_id
            ctk.CTkButton(
                row,
                text=chat["title"],
                command=lambda cid=chat["id"]: self.load_chat(cid),
                font=ctk.CTkFont(size=12),
                fg_color="#1e1e1e" if is_active else "transparent",
                text_color="#e8e8e8",
                hover_color="#1e1e1e",
                anchor="w",
                height=32
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row,
                text="✕",
                command=lambda cid=chat["id"]: self.delete_chat(cid),
                font=ctk.CTkFont(size=10),
                fg_color="transparent",
                text_color="#555",
                hover_color="#2a2a2a",
                width=24, height=32
            ).pack(side="right")

    # ── UI ──
    def build_ui(self):
        # LOGIN FRAME
        self.login_frame = ctk.CTkFrame(self, fg_color="#0a0a0a")

        ctk.CTkLabel(
            self.login_frame,
            text="N.A.V.I",
            font=ctk.CTkFont(family="Courier New", size=42, weight="bold"),
            text_color="#e8e8e8"
        ).pack(pady=(80, 4))

        ctk.CTkLabel(
            self.login_frame,
            text="NEURAL ADAPTIVE VIRTUAL INTELLIGENCE",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#444"
        ).pack(pady=(0, 40))

        # Вкладки
        tabs_frame = ctk.CTkFrame(self.login_frame, fg_color="#141414", corner_radius=8)
        tabs_frame.pack(padx=80, fill="x", pady=(0, 10))

        self._login_tab = ctk.StringVar(value="creator")

        self.tab_creator_btn = ctk.CTkButton(
            tabs_frame, text="Создатель",
            command=lambda: self._switch_login_tab("creator"),
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="#e8e8e8", text_color="#0a0a0a",
            hover_color="#cccccc", height=34, corner_radius=6
        )
        self.tab_creator_btn.pack(side="left", fill="x", expand=True, padx=(4,2), pady=4)

        self.tab_guest_btn = ctk.CTkButton(
            tabs_frame, text="Гость",
            command=lambda: self._switch_login_tab("guest"),
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color="transparent", text_color="#555",
            hover_color="#1a1a1a", height=34, corner_radius=6
        )
        self.tab_guest_btn.pack(side="left", fill="x", expand=True, padx=(2,4), pady=4)

        # Панель создателя
        self.panel_creator = ctk.CTkFrame(self.login_frame, fg_color="#141414", corner_radius=10)
        self.panel_creator.pack(padx=80, fill="x", pady=(0, 10))

        ctk.CTkLabel(self.panel_creator, text="API КЛЮЧ (GROQ)",
            font=ctk.CTkFont(family="Courier New", size=10), text_color="#555"
        ).pack(anchor="w", padx=20, pady=(16, 4))

        self.key_entry = ctk.CTkEntry(self.panel_creator,
            placeholder_text="gsk_xxxxxxxxxxxxxxxx", show="*",
            font=ctk.CTkFont(family="Courier New", size=13),
            fg_color="#1a1a1a", border_color="#2a2a2a",
            text_color="#e8e8e8", height=44)
        self.key_entry.pack(padx=16, pady=(0, 16), fill="x")
        self.key_entry.bind("<Return>", lambda e: self.do_login())
        self.key_entry.bind("<Control-v>", lambda e: self._paste_to(self.key_entry))
        self.key_entry.bind("<Control-V>", lambda e: self._paste_to(self.key_entry))

        # Панель гостя
        self.panel_guest = ctk.CTkFrame(self.login_frame, fg_color="#141414", corner_radius=10)

        ctk.CTkLabel(self.panel_guest, text="ГОСТЕВОЙ КОД",
            font=ctk.CTkFont(family="Courier New", size=10), text_color="#555"
        ).pack(anchor="w", padx=20, pady=(16, 4))

        self.guest_code_entry = ctk.CTkEntry(self.panel_guest,
            placeholder_text="Код от создателя", show="*",
            font=ctk.CTkFont(family="Courier New", size=13),
            fg_color="#1a1a1a", border_color="#2a2a2a",
            text_color="#e8e8e8", height=44)
        self.guest_code_entry.pack(padx=16, pady=(0, 8), fill="x")

        ctk.CTkLabel(self.panel_guest, text="API КЛЮЧ (GROQ)",
            font=ctk.CTkFont(family="Courier New", size=10), text_color="#555"
        ).pack(anchor="w", padx=20)

        self.guest_key_entry = ctk.CTkEntry(self.panel_guest,
            placeholder_text="gsk_xxxxxxxxxxxxxxxx", show="*",
            font=ctk.CTkFont(family="Courier New", size=13),
            fg_color="#1a1a1a", border_color="#2a2a2a",
            text_color="#e8e8e8", height=44)
        self.guest_key_entry.pack(padx=16, pady=(4, 16), fill="x")
        self.guest_key_entry.bind("<Return>", lambda e: self.do_login())
        self.guest_code_entry.bind("<Control-v>", lambda e: self._paste_to(self.guest_code_entry))
        self.guest_code_entry.bind("<Control-V>", lambda e: self._paste_to(self.guest_code_entry))
        self.guest_key_entry.bind("<Control-v>", lambda e: self._paste_to(self.guest_key_entry))
        self.guest_key_entry.bind("<Control-V>", lambda e: self._paste_to(self.guest_key_entry))

        self.login_error = ctk.CTkLabel(self.login_frame, text="",
            font=ctk.CTkFont(size=11), text_color="#ff4444")
        self.login_error.pack()

        ctk.CTkButton(
            self.login_frame, text="ВОЙТИ",
            command=self.do_login,
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            fg_color="#e8e8e8", text_color="#0a0a0a",
            hover_color="#cccccc", height=46, corner_radius=8
        ).pack(padx=80, fill="x", pady=(10, 0))

        # APP FRAME
        self.app_frame = ctk.CTkFrame(self, fg_color="#0a0a0a")

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self.app_frame, fg_color="#111", width=240, corner_radius=0)

        self.sb_header_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="#111")
        sb_header = self.sb_header_frame
        sb_header.pack(fill="x", padx=12, pady=(16, 8))

        ctk.CTkLabel(
            sb_header,
            text="N.A.V.I",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            text_color="#e8e8e8"
        ).pack(side="left")

        ctk.CTkButton(
            sb_header,
            text="✕",
            command=lambda: self.sidebar_frame.pack_forget(),
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color="#555",
            hover_color="#1a1a1a",
            width=28, height=28
        ).pack(side="right")

        ctk.CTkButton(
            self.sidebar_frame,
            text="+ Новый чат",
            command=self.new_chat,
            font=ctk.CTkFont(size=13),
            fg_color="#1a1a1a",
            text_color="#e8e8e8",
            hover_color="#242424",
            height=36,
            corner_radius=8
        ).pack(padx=12, fill="x", pady=(0, 8))

        ctk.CTkLabel(
            self.sidebar_frame,
            text="НЕДАВНИЕ",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color="#444"
        ).pack(anchor="w", padx=16, pady=(4, 2))

        self.chat_list_frame = ctk.CTkScrollableFrame(
            self.sidebar_frame,
            fg_color="#111",
            scrollbar_button_color="#222"
        )
        self.chat_list_frame.pack(fill="both", expand=True, padx=4)

        # Chat area
        self.chat_area = ctk.CTkFrame(self.app_frame, fg_color="#0a0a0a")
        self.chat_area.pack(fill="both", expand=True)

        # Header
        self.header_frame = ctk.CTkFrame(self.chat_area, fg_color="#0a0a0a", height=50)
        header = self.header_frame
        header.pack(fill="x", padx=16, pady=(10, 0))
        header.pack_propagate(False)

        ctk.CTkButton(
            header,
            text="☰",
            command=self.toggle_sidebar,
            font=ctk.CTkFont(size=16),
            fg_color="transparent",
            text_color="#555",
            hover_color="#1a1a1a",
            width=32, height=32
        ).pack(side="left", pady=8)

        ctk.CTkLabel(
            header,
            text="N.A.V.I",
            font=ctk.CTkFont(family="Courier New", size=15, weight="bold"),
            text_color="#e8e8e8"
        ).pack(side="left", padx=10, pady=8)

        self.status_label = ctk.CTkLabel(
            header,
            text="● online",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#44cc88"
        )
        self.status_label.pack(side="left", padx=(4,0), pady=8)

        # ── Меню "···" ──
        self.menu_frame = ctk.CTkFrame(header, fg_color="transparent")
        self.menu_frame.pack(side="right", pady=8)

        self._menu_open = False
        self._menu_popup = None

        self.menu_btn = ctk.CTkButton(
            self.menu_frame, text="···",
            command=self._toggle_menu,
            font=ctk.CTkFont(family="Courier New", size=18),
            fg_color="transparent", text_color="#888",
            hover_color="#1a1a1a", width=36, height=36, corner_radius=8)
        self.menu_btn.pack()

        # Mute btn (скрытая, нужна для toggle_mute)
        self.mute_btn = ctk.CTkButton(self, text="🔊", width=0, height=0,
            fg_color="transparent", command=self.toggle_mute)
        # voice_btn placeholder (не используется в меню)
        self.voice_btn = ctk.CTkButton(self, text="🎤", width=0, height=0,
            fg_color="transparent", command=self.toggle_voice)

        ctk.CTkFrame(self.chat_area, fg_color="#222", height=1).pack(fill="x")

        self.guest_badge = ctk.CTkLabel(
            self.chat_area,
            text="гостевой доступ",
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color="#555",
            fg_color="#111",
            anchor="w"
        )
        # shown only for guests

        self.messages_frame = ctk.CTkScrollableFrame(
            self.chat_area,
            fg_color="#0a0a0a",
            scrollbar_button_color="#222",
            scrollbar_button_hover_color="#333"
        )
        self.messages_frame.pack(fill="both", expand=True)

        ctk.CTkFrame(self.chat_area, fg_color="#222", height=1).pack(fill="x")

        self.files_label = ctk.CTkLabel(
            self.chat_area,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#888",
            anchor="w"
        )

        self.input_area_frame = ctk.CTkFrame(self.chat_area, fg_color="#0a0a0a")
        input_area = self.input_area_frame
        input_area.pack(fill="x", padx=16, pady=10)

        ctk.CTkButton(
            input_area,
            text="📎",
            command=self.attach_file,
            font=ctk.CTkFont(size=14),
            fg_color="#141414",
            text_color="#888",
            hover_color="#1e1e1e",
            width=40, height=40,
            corner_radius=8
        ).pack(side="left", padx=(0, 8))

        self.msg_input = ctk.CTkTextbox(
            input_area,
            height=40,
            font=ctk.CTkFont(size=14),
            fg_color="#141414",
            border_color="#2a2a2a",
            text_color="#e8e8e8",
            border_width=1,
            corner_radius=8,
            wrap="word"
        )
        self.msg_input.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.msg_input.bind("<Return>", self.on_enter)

        self.send_btn = ctk.CTkButton(
            input_area,
            text="отправить",
            command=self.send_message,
            font=ctk.CTkFont(family="Courier New", size=10, weight="bold"),
            fg_color="#e8e8e8",
            text_color="#0a0a0a",
            hover_color="#cccccc",
            height=40, width=110,
            corner_radius=8
        )
        self.send_btn.pack(side="right")

    def toggle_sidebar(self):
        if self.sidebar_frame.winfo_ismapped():
            self.sidebar_frame.pack_forget()
        else:
            self.save_current_chat()
            self.refresh_chat_list()
            self.sidebar_frame.pack(side="left", fill="y", before=self.chat_area)

    def show_login(self):
        self.app_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True)

    def show_chat(self):
        self.login_frame.pack_forget()
        self.app_frame.pack(fill="both", expand=True)

    def _paste_to(self, entry):
        try:
            text = self.clipboard_get()
            entry.delete(0, "end")
            entry.insert(0, text.strip())
        except:
            pass
        return "break"

    def _switch_login_tab(self, tab):
        self._login_tab.set(tab)
        if tab == "creator":
            self.panel_creator.pack(padx=80, fill="x", pady=(0, 10))
            self.panel_guest.pack_forget()
            self.tab_creator_btn.configure(fg_color="#e8e8e8", text_color="#0a0a0a")
            self.tab_guest_btn.configure(fg_color="transparent", text_color="#555")
        else:
            self.panel_guest.pack(padx=80, fill="x", pady=(0, 10))
            self.panel_creator.pack_forget()
            self.tab_guest_btn.configure(fg_color="#e8e8e8", text_color="#0a0a0a")
            self.tab_creator_btn.configure(fg_color="transparent", text_color="#555")

    def _sha256(self, text):
        import hashlib
        return hashlib.sha256(text.encode()).hexdigest()

    def get_guest_uploads(self):
        try:
            with open(GUEST_UPLOADS_FILE, "r") as f:
                d = json.load(f)
            if datetime.now().timestamp() - d.get("reset", 0) > 86400:
                return {"count": 0, "reset": datetime.now().timestamp()}
            return d
        except:
            return {"count": 0, "reset": datetime.now().timestamp()}

    def increment_guest_uploads(self):
        d = self.get_guest_uploads()
        d["count"] = d.get("count", 0) + 1
        if not d.get("reset"):
            d["reset"] = datetime.now().timestamp()
        with open(GUEST_UPLOADS_FILE, "w") as f:
            json.dump(d, f)

    def do_login(self):
        tab = self._login_tab.get()

        if tab == "creator":
            key = self.key_entry.get().strip()
            if not key:
                self.login_error.configure(text="Введи API ключ")
                return
            if not key.startswith("gsk_") or len(key) < 40:
                self.login_error.configure(text="Неверный формат ключа")
                return
            self.login_error.configure(text="Проверка ключа...")
            self.update()
            try:
                test_client = Groq(api_key=key)
                test_client.models.list()
            except:
                self.login_error.configure(text="Ключ недействителен")
                return
            self.api_key = key
            self.is_guest = False
            self.client = Groq(api_key=key)
            with open(CREATOR_KEY_FILE, "w") as f:
                f.write(key)
            self.show_chat()
            self.new_chat(silent=True)
            self.add_message("navi", "N.A.V.I онлайн. Чем могу помочь?")

        else:
            # Гость
            code = self.guest_code_entry.get().strip()
            if not code:
                self.login_error.configure(text="Введи гостевой код")
                return
            if self._sha256(code) != GUEST_CODE_HASH:
                self.login_error.configure(text="Неверный код")
                return
            key = self.guest_key_entry.get().strip()
            if not key:
                self.login_error.configure(text="Введи API ключ")
                return
            if not key.startswith("gsk_") or len(key) < 40:
                self.login_error.configure(text="Неверный формат ключа")
                return
            self.login_error.configure(text="Проверка ключа...")
            self.update()
            try:
                test_client = Groq(api_key=key)
                test_client.models.list()
            except:
                self.login_error.configure(text="Ключ недействителен")
                return
            self.api_key = key
            self.is_guest = True
            self.client = Groq(api_key=key)
            self.show_chat()
            self.guest_badge.pack(fill="x", padx=0, pady=0, before=self.messages_frame)
            self.new_chat(silent=True)
            self.add_message("navi", "Гостевой доступ активирован. Чем могу помочь?")

    def logout(self):
        self.voice_active = False
        if self._monitor_window and self._monitor_window.winfo_exists():
            self._monitor_window.destroy()
        if self._weather_window and self._weather_window.winfo_exists():
            self._weather_window.destroy()
        if self._notes_window and self._notes_window.winfo_exists():
            self._notes_window.destroy()
        if self._game_window and self._game_window.winfo_exists():
            self._game_window.destroy()
        if self._game_window and self._game_window.winfo_exists():
            self._game_window.destroy()
        if os.path.exists(CREATOR_KEY_FILE):
            os.remove(CREATOR_KEY_FILE)
        self.api_key = ""
        self.client = None
        self.history = []
        for w in self.messages_frame.winfo_children():
            w.destroy()
        self.show_login()

    # ── MONITOR ──
    def open_monitor(self):
        if self._monitor_window and self._monitor_window.winfo_exists():
            self._monitor_window.focus()
            return
        self._monitor_window = SystemMonitorWindow(self)
        self._monitor_window.focus()

    # ── WEATHER ──
    def open_weather(self):
        if self._weather_window and self._weather_window.winfo_exists():
            self._weather_window.focus()
            return
        self._weather_window = WeatherWindow(self)
        self._weather_window.focus()

    def open_notes(self):
        if self._notes_window and self._notes_window.winfo_exists():
            self._notes_window.focus()
            return
        self._notes_window = NotesWindow(self)
        self._notes_window.focus()

    def _toggle_menu(self):
        if self._menu_open:
            self._close_menu()
        else:
            self._open_menu()

    def _open_menu(self):
        if self._menu_open:
            return
        self._menu_open = True
        t = THEMES[self.current_theme]

        # Создаём popup окно
        popup = ctk.CTkToplevel(self)
        popup.overrideredirect(True)
        popup.configure(fg_color="#1c1c1c")
        popup.attributes("-topmost", True)
        self._menu_popup = popup

        btn_cfg = dict(
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            text_color=t["text"],
            hover_color="#2a2a2a",
            anchor="w", height=38, corner_radius=0
        )

        def cmd(fn):
            popup.destroy()
            self._menu_open = False
            fn()

        mute_text = "🔇  Выключить звук" if not self.is_muted else "🔊  Включить звук"
        ctk.CTkButton(popup, text=mute_text,
            command=lambda: cmd(self.toggle_mute), **btn_cfg).pack(fill="x", padx=2, pady=(4,0))

        if SR_AVAILABLE:
            voice_text = "⏹  Выкл. голос" if self.voice_active else "🎤  Вкл. голос"
            ctk.CTkButton(popup, text=voice_text,
                command=lambda: cmd(self.toggle_voice), **btn_cfg).pack(fill="x", padx=2)

        ctk.CTkButton(popup, text="⬡  Монитор системы",
            command=lambda: cmd(self.open_monitor), **btn_cfg).pack(fill="x", padx=2)
        ctk.CTkButton(popup, text="🌤  Погода",
            command=lambda: cmd(self.open_weather), **btn_cfg).pack(fill="x", padx=2)
        ctk.CTkButton(popup, text="📝  Заметки",
            command=lambda: cmd(self.open_notes), **btn_cfg).pack(fill="x", padx=2)
        ctk.CTkButton(popup, text="⚡  Overclocked",
            command=lambda: cmd(self.open_game), **btn_cfg).pack(fill="x", padx=2)
        ctk.CTkButton(popup, text="⚡  Overclocked",
            command=lambda: cmd(self.open_game), **btn_cfg).pack(fill="x", padx=2)

        names = {"dark":"Тёмная","gray":"Серая","light":"Светлая"}
        next_t = {"dark":"gray","gray":"light","light":"dark"}[self.current_theme]
        ctk.CTkButton(popup, text=f"◑  Тема → {names[next_t]}",
            command=lambda: cmd(self.cycle_theme), **btn_cfg).pack(fill="x", padx=2)

        ctk.CTkFrame(popup, fg_color="#333", height=1).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(popup, text="↩  Выйти",
            command=lambda: cmd(self.logout),
            font=ctk.CTkFont(size=14), fg_color="transparent",
            text_color="#ff5555", hover_color="#2a2a2a",
            anchor="w", height=38, corner_radius=0).pack(fill="x", padx=2, pady=(0,4))

        # Позиция под кнопкой ···
        self.update_idletasks()
        popup.update_idletasks()
        wx = self.winfo_rootx()
        wy = self.winfo_rooty()
        ww = self.winfo_width()
        pw = 210
        ph = popup.winfo_reqheight()
        px = wx + ww - pw - 10
        py = wy + 58
        popup.geometry(f"{pw}x{ph}+{px}+{py}")

        # Закрыть при клике вне меню
        popup.bind("<FocusOut>", lambda e: self._close_menu())

    def _close_menu(self):
        self._menu_open = False
        try:
            if self._menu_popup and self._menu_popup.winfo_exists():
                self._menu_popup.destroy()
        except: pass

    def _check_close_menu(self, event):
        pass

    def cycle_theme(self):
        order = ["dark", "gray", "light"]
        idx = order.index(self.current_theme)
        self.current_theme = order[(idx + 1) % len(order)]
        try:
            with open(THEME_FILE, "w") as f:
                f.write(self.current_theme)
        except: pass
        self.apply_theme()
        names = {"dark": "Тёмная", "gray": "Серая", "light": "Светлая"}
        self.add_message("navi", f"Тема: {names[self.current_theme]}")

    def apply_theme(self):
        t = THEMES[self.current_theme]
        ctk.set_appearance_mode(t["mode"])
        self.configure(fg_color=t["bg"])
        self.app_frame.configure(fg_color=t["bg"])
        self.login_frame.configure(fg_color=t["bg"])
        self.chat_area.configure(fg_color=t["bg"])
        self.sidebar_frame.configure(fg_color=t["sidebar"])
        self.messages_frame.configure(fg_color=t["bg"])
        self.msg_input.configure(
            fg_color=t["input_bg"],
            border_color=t["border_light"],
            text_color=t["text"])
        self.send_btn.configure(
            fg_color=t["send_btn"],
            text_color=t["send_btn_text"],
            hover_color=t["border"])
        self.status_label.configure(text_color="#44cc88")
        # Перекрасить хедер и input
        try: self.header_frame.configure(fg_color=t["bg"])
        except: pass
        try: self.input_area_frame.configure(fg_color=t["bg"])
        except: pass
        try: self.sb_header_frame.configure(fg_color=t["sidebar"])
        except: pass
        try: self.chat_list_frame.configure(fg_color=t["sidebar"])
        except: pass
        # Перекрасить все существующие сообщения
        for frame in self.messages_frame.winfo_children():
            try:
                frame.configure(fg_color=t["bg"])
                children = frame.winfo_children()
                if len(children) >= 2:
                    # meta label
                    children[0].configure(text_color=t["text_dim"])
                    # text label — определяем роль по тексту meta
                    meta_text = children[0].cget("text")
                    if meta_text == "система":
                        children[1].configure(text_color="#ff4444")
                    elif meta_text == "ты":
                        children[1].configure(text_color=t["text_dim"])
                    else:
                        children[1].configure(text_color=t["text"])
            except:
                pass

    def open_game(self):
        if self._game_window and self._game_window.winfo_exists():
            self._game_window.focus()
            return
        self._game_window = GameWindow(self)
        self._game_window.focus()

    def open_game(self):
        if self._game_window and self._game_window.winfo_exists():
            self._game_window.focus()
            return
        self._game_window = GameWindow(self)
        self._game_window.focus()

    def add_note(self, text):
        try:
            notes = []
            if os.path.exists(NOTES_FILE):
                with open(NOTES_FILE, "r", encoding="utf-8") as f:
                    notes = json.load(f)
            notes.insert(0, {
                "text": text,
                "date": datetime.now().strftime("%d.%m.%Y %H:%M")
            })
            with open(NOTES_FILE, "w", encoding="utf-8") as f:
                json.dump(notes[:100], f, ensure_ascii=False, indent=2)
            if self._notes_window and self._notes_window.winfo_exists():
                self._notes_window.refresh()
        except Exception as e:
            print(f"Note save error: {e}")

    # ── MESSAGES ──
    def add_message(self, role, text):
        t = THEMES[self.current_theme]
        frame = ctk.CTkFrame(self.messages_frame, fg_color=t["bg"])
        frame.pack(fill="x", padx=20, pady=(0, 14))
        meta = "N.A.V.I" if role == "navi" else "ты" if role == "user" else "система"
        ctk.CTkLabel(
            frame,
            text=meta,
            font=ctk.CTkFont(family="Courier New", size=9),
            text_color=t["text_dim"],
            anchor="w" if role != "user" else "e"
        ).pack(fill="x")
        if role == "navi":
            msg_color = t["text"]
        elif role == "user":
            msg_color = t["text_dim"]
        else:
            msg_color = "#ff4444"
        ctk.CTkLabel(
            frame,
            text=text,
            font=ctk.CTkFont(size=16),
            text_color=msg_color,
            wraplength=750,
            justify="left" if role != "user" else "right",
            anchor="w" if role != "user" else "e"
        ).pack(fill="x")
        self.after(50, lambda: self.messages_frame._parent_canvas.yview_moveto(1.0))

    # ── COMMANDS ──

    def _launch_app(self, app_name):
        import os, subprocess

        name_lower = app_name.lower()

        known = {
            "стим": "steam", "steam": "steam",
            "дискорд": "Discord", "discord": "Discord",
            "телеграм": "Telegram", "telegram": "Telegram",
            "хром": "chrome", "chrome": "chrome", "гугл хром": "chrome",
            "edge": "msedge", "эдж": "msedge",
            "obs": "obs64", "obs studio": "obs64",
            "vscode": "Code", "visual studio code": "Code", "vs code": "Code",
            "rust": "rust",
            "роблокс": "RobloxPlayerBeta", "roblox": "RobloxPlayerBeta",
            "роблокс студио": "RobloxStudio", "roblox studio": "RobloxStudio",
            "юнити хаб": "Unity Hub", "unity hub": "Unity Hub",
            "capcut": "CapCut", "кэпкат": "CapCut",
            "soundpad": "Soundpad", "саундпад": "Soundpad",
            "repo": "REPO", "р.е.п.о": "REPO",
            "paragnosia": "Paragnosia", "парагнозия": "Paragnosia",
            "peak": "PEAK",
            "евро трак": "eurotrucks2", "euro truck": "eurotrucks2",
            "transport fever": "TransportFever2",
            "spaceflight": "Spaceflight Simulator",
            "metro exodus": "MetroExodus",
            "scp": "SCPCB", "scp containment": "SCPCB",
            "plague inc": "Plague Inc",
            "buckshot": "BuckshotRoulette",
            "geometry dash": "GeometryDash",
        }

        exe_hint = known.get(name_lower, name_lower.replace(" ", ""))

        # Прямые пути для известных программ
        direct_paths = {
            "стим": os.path.join("D:", os.sep, "Steam", "steam.exe"),
            "steam": os.path.join("D:", os.sep, "Steam", "steam.exe"),
        }
        if name_lower in direct_paths:
            path = direct_paths[name_lower]
            if os.path.exists(path):
                try:
                    subprocess.Popen(f'"{path}"', shell=True)
                    reply = f"Запускаю {app_name}."
                    self.add_message("navi", reply)
                    if not self.is_muted:
                        speak_text("Запускаю.")
                    return True
                except Exception:
                    pass

        # Прямые пути для известных программ
        direct_paths = {
            "стим": os.path.join("D:", os.sep, "Steam", "steam.exe"),
            "steam": os.path.join("D:", os.sep, "Steam", "steam.exe"),
        }
        if name_lower in direct_paths:
            path = direct_paths[name_lower]
            if os.path.exists(path):
                try:
                    subprocess.Popen(f'"{path}"', shell=True)
                    reply = f"Запускаю {app_name}."
                    self.add_message("navi", reply)
                    if not self.is_muted:
                        speak_text("Запускаю.")
                    return True
                except Exception:
                    pass

        home = os.path.expanduser("~")
        search_dirs = [
            os.path.join("C:", os.sep, "Program Files"),
            os.path.join("C:", os.sep, "Program Files (x86)"),
            os.path.join("C:", os.sep, "Users", "cuttl", "AppData", "Local", "Roblox"),
            os.path.join("D:", os.sep),
            os.path.join("D:", os.sep, "Steam"),
            os.path.join("D:", os.sep, "Steam", "steamapps", "common"),
            os.path.join("D:", os.sep, "SteamLibrary", "steamapps", "common"),
            os.path.join(home, "AppData", "Local"),
            os.path.join(home, "AppData", "Roaming"),
            os.path.join(home, "Desktop"),
            os.path.join("C:", os.sep, "ProgramData", "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(home, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs"),
        ]

        # 1. Поиск .exe
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
            for root, dirs, files in os.walk(search_dir):
                for f in files:
                    if f.lower().endswith(".exe"):
                        fname = f.lower().replace(".exe", "")
                        if (exe_hint.lower() in fname or
                                fname in exe_hint.lower() or
                                name_lower.replace(" ", "") in fname):
                            full_path = os.path.join(root, f)
                            try:
                                subprocess.Popen(f'"{full_path}"', shell=True)
                                reply = f"Запускаю {app_name}."
                                self.add_message("navi", reply)
                                if not self.is_muted:
                                    speak_text("Запускаю.")
                                return True
                            except Exception:
                                pass
                depth = root.replace(search_dir, "").count(os.sep)
                if depth >= 3:
                    dirs.clear()

        # 2. Поиск ярлыков .lnk
        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue
            try:
                for f in os.listdir(search_dir):
                    if f.lower().endswith(".lnk"):
                        fname = f.lower().replace(".lnk", "")
                        if name_lower in fname or fname in name_lower:
                            try:
                                os.startfile(os.path.join(search_dir, f))
                                reply = f"Запускаю {app_name}."
                                self.add_message("navi", reply)
                                if not self.is_muted:
                                    speak_text("Запускаю.")
                                return True
                            except Exception:
                                pass
            except Exception:
                pass

        # 3. Попробовать через shell как последний вариант
        try:
            subprocess.Popen(exe_hint, shell=True)
            reply = f"Запускаю {app_name}."
            self.add_message("navi", reply)
            if not self.is_muted:
                speak_text("Запускаю.")
            return True
        except Exception:
            pass

        reply = f"Не нашла программу: {app_name}. Попробуй уточнить название."
        self.add_message("navi", reply)
        return True

    def handle_command(self, text):
        m = text.lower().strip()

        if m in ["время", "который час", "сколько времени", "сколько сейчас времени"]:
            reply = f"Сейчас {datetime.now().strftime('%H:%M')}"
            self.add_message("navi", reply)
            if not self.is_muted:
                speak_text(reply)
            return True

        if any(x in m for x in ["монитор", "мониторинг", "системный монитор", "открой монитор", "покажи монитор"]):
            self.open_monitor()
            reply = "Открываю монитор системы."
            self.add_message("navi", reply)
            if not self.is_muted:
                speak_text(reply)
            return True

        # ── ПОГОДА ──
        if any(x in m for x in [
            "погода", "какая погода", "какая сегодня погода", "прогноз погоды",
            "прогноз", "погода сегодня", "открой погоду", "покажи погоду",
            "что с погодой", "как погода", "температура на улице"
        ]):
            self.open_weather()
            reply = "Открываю прогноз погоды."
            self.add_message("navi", reply)
            if not self.is_muted:
                speak_text(reply)
            return True

        # ── ЗАМЕТКИ ──
        if m.startswith("запомни ") or m.startswith("запомни:"):
            note_text = text.strip()
            for prefix in ["запомни:", "запомни "]:
                if note_text.lower().startswith(prefix):
                    note_text = note_text[len(prefix):].strip()
                    break
            if note_text:
                self.add_note(note_text)
                reply = f"Запомнила: {note_text}"
                self.add_message("navi", reply)
                if not self.is_muted:
                    speak_text("Запомнила.")
                return True

        if any(x in m for x in ["заметки", "покажи заметки", "мои заметки", "открой заметки"]):
            self.open_notes()
            reply = "Открываю заметки."
            self.add_message("navi", reply)
            if not self.is_muted:
                speak_text(reply)
            return True

        if any(x in m for x in ["состояние пк", "статус пк", "состояние компьютера", "проверь пк", "как пк"]):
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage('C:\\')
            ram_used = round(ram.used / (1024**3), 1)
            ram_total = round(ram.total / (1024**3), 1)
            disk_used = round(disk.used / (1024**3), 1)
            disk_total = round(disk.total / (1024**3), 1)
            try:
                temps = psutil.sensors_temperatures()
                temp_str = ""
                for name, entries in temps.items():
                    for entry in entries:
                        temp_str = f", температура {round(entry.current)}°C"
                        break
                    break
            except:
                temp_str = ""
            # GPU
            gpu_str = ""
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    g = gpus[0]
                    gpu_str = f"\nGPU: {g.name} — {int((g.load or 0)*100)}% нагрузка, {g.temperature}°C"
            except:
                pass
            # Disk D
            disk_d_str = ""
            try:
                dd = psutil.disk_usage('D:\\')
                disk_d_str = f"\nДиск D: {round(dd.used/(1024**3),1)}GB / {round(dd.total/(1024**3),1)}GB ({dd.percent}%)"
            except:
                pass
            reply = (
                f"Состояние системы:\n"
                f"CPU: {cpu}%{temp_str}\n"
                f"RAM: {ram_used}GB / {ram_total}GB ({ram.percent}%)\n"
                f"Диск C: {disk_used}GB / {disk_total}GB ({disk.percent}%)"
                f"{disk_d_str}{gpu_str}"
            )
            self.add_message("navi", reply)
            if not self.is_muted:
                speak_text(f"CPU {cpu} процентов, RAM {ram.percent} процентов, диск {disk.percent} процентов")
            return True

        sites = {
            "ютуб": "https://youtube.com",
            "youtube": "https://youtube.com",
            "гугл": "https://google.com",
            "google": "https://google.com",
            "инстаграм": "https://instagram.com",
            "телеграм": "https://web.telegram.org",
            "музыку": "https://music.youtube.com",
            "музыка": "https://music.youtube.com",
            "нетфликс": "https://netflix.com",
            "тикток": "https://tiktok.com",
        }
        if m.startswith("открой ") or m.startswith("перейди на "):
            for key, url in sites.items():
                if key in m:
                    if self.is_guest:
                        reply = "Открытие сайтов недоступно в гостевом режиме."
                        self.add_message("navi", reply)
                        return True
                    webbrowser.open(url)
                    reply = f"Открываю {key}."
                    self.add_message("navi", reply)
                    if not self.is_muted:
                        speak_text(reply)
                    return True

        programs = {
            "калькулятор": "calc",
            "блокнот": "notepad",
            "проводник": "explorer",
            "диспетчер задач": "taskmgr",
        }
        if m.startswith("открой ") or m.startswith("запусти "):
            for key, cmd in programs.items():
                if key in m:
                    subprocess.Popen(cmd)
                    reply = f"Запускаю {key}."
                    self.add_message("navi", reply)
                    if not self.is_muted:
                        speak_text(reply)
                    return True
            # Поиск любой программы
            app_name = text.strip()
            for prefix in ["запусти ", "открой "]:
                if app_name.lower().startswith(prefix):
                    app_name = app_name[len(prefix):].strip()
                    break
            if app_name:
                self._launch_app(app_name)
                return True

        return False

    # ── SEND ──
    def on_enter(self, event):
        if not event.state & 0x1:
            self.send_message()
            return "break"

    def send_message(self, voice_text=None):
        if self.is_loading:
            return
        text = voice_text or self.msg_input.get("1.0", "end").strip()
        if not text and not self.pending_files:
            return
        if not voice_text:
            self.msg_input.delete("1.0", "end")

        if self.pending_files:
            self.send_with_files(text)
            return

        if self.handle_command(text):
            return

        self.add_message("user", text)
        self.history.append({"role": "user", "content": text})
        self.start_loading()
        threading.Thread(target=self.get_response, daemon=True).start()

    def send_with_files(self, text):
        files = [f for f in self.pending_files if f]
        self.pending_files = []
        self.files_label.configure(text="")
        self.files_label.pack_forget()

        images = [f for f in files if f["type"] == "image"]
        docs = [f for f in files if f["type"] == "file"]

        # Гостевой лимит фото
        if self.is_guest and images:
            uploads = self.get_guest_uploads()
            remaining = 3 - uploads.get("count", 0)
            if remaining <= 0:
                reset_in = max(1, int((uploads.get("reset", 0) + 86400 - datetime.now().timestamp()) / 3600))
                self.add_message("navi", f"Лимит фото исчерпан (3/3 в день). Доступно снова через ~{reset_in} ч.")
                return
            if len(images) > remaining:
                self.add_message("navi", f"Можно загрузить ещё {remaining} фото сегодня. Отправляю только первые {remaining}.")
                images = images[:remaining]
            for _ in images:
                self.increment_guest_uploads()

        display = text or ("📎 " + ", ".join(f["name"] for f in files))
        self.add_message("user", display)

        content = []
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": f"data:{img['mime']};base64,{img['data']}"}})

        file_text = "".join(f"[Файл: {d['name']}]\n{d['data'][:8000]}\n\n" for d in docs)
        full_text = (text or "Что на этом изображении?") + ("\n\n" + file_text if file_text else "")
        content.append({"type": "text", "text": full_text})

        self.history.append({"role": "user", "content": content})
        self.start_loading()
        threading.Thread(target=lambda: self.get_response(vision=bool(images)), daemon=True).start()

    def start_loading(self):
        self.is_loading = True
        self.send_btn.configure(state="disabled", text="...")
        self.status_label.configure(text="● думает...", text_color="#888")

    def get_response(self, vision=False):
        try:
            model = "meta-llama/llama-4-scout-17b-16e-instruct" if vision else "llama-3.3-70b-versatile"
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history[-20:]
            response = self.client.chat.completions.create(
                model=model, messages=messages, max_tokens=1024, temperature=0.7
            )
            reply = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": reply})
            self.after(0, lambda: self.on_response(reply))
        except Exception as e:
            self.after(0, lambda: self.on_error(str(e)))

    def on_response(self, reply):
        self.add_message("navi", reply)
        self.is_loading = False
        self.send_btn.configure(state="normal", text="отправить")
        self.status_label.configure(text="● online", text_color="#44cc88")
        self.save_current_chat()
        if not self.is_muted:
            speak_text(reply)

    def on_error(self, error):
        self.add_message("sys", f"Ошибка: {error}")
        self.is_loading = False
        self.send_btn.configure(state="normal", text="отправить")
        self.status_label.configure(text="● online", text_color="#44cc88")

    # ── MUTE ──
    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.mute_btn.configure(text="🔇" if self.is_muted else "🔊")
        self.add_message("navi", "Режим без звука включён." if self.is_muted else "Звук включён.")

    # ── VOICE ──
    def toggle_voice(self):
        if self.voice_active:
            self.stop_voice()
        else:
            self.start_voice()

    def start_voice(self):
        self.voice_active = True
        self.status_label.configure(text="● голосовой режим", text_color="#4488ff")
        self.add_message("navi", "Голосовой режим включён. Скажи НАВИ — и я отвечу.")
        threading.Thread(target=self.voice_loop, daemon=True).start()

    def stop_voice(self):
        self.voice_active = False
        self.status_label.configure(text="● online", text_color="#44cc88")
        self.add_message("navi", "Голосовой режим выключен.")

    def voice_loop(self):
        import sounddevice as sd
        import numpy as np
        import io, wave, urllib.request, json as _json

        RATE = 16000
        CHUNK = 1024
        SILENCE_THRESHOLD = 200  # порог голоса
        MAX_SILENCE_CHUNKS = 20  # ~1.3 сек тишины
        MAX_RECORD_CHUNKS = 120  # ~8 сек максимум

        wake_words = [
            "нави", "navi", "navy", "навий", "навии",
            "навигатор", "нэви", "наби",
        ]

        def rms(data):
            if len(data) == 0:
                return 0
            return float(np.sqrt(np.mean(np.square(data.astype(np.float64)))))

        def record_phrase():
            frames = []
            silent_chunks = 0
            recording = False
            total_chunks = 0

            with sd.InputStream(samplerate=RATE, channels=1,
                               dtype='int16', blocksize=CHUNK) as stream:
                while self.voice_active:
                    data, _ = stream.read(CHUNK)
                    flat = data.flatten()
                    level = rms(flat)

                    if level > SILENCE_THRESHOLD:
                        recording = True
                        silent_chunks = 0
                        frames.append(flat.tobytes())
                        total_chunks += 1
                    elif recording:
                        frames.append(flat.tobytes())
                        silent_chunks += 1
                        total_chunks += 1
                        if silent_chunks > MAX_SILENCE_CHUNKS:
                            break

                    if total_chunks > MAX_RECORD_CHUNKS:
                        break

            if not frames or total_chunks < 5:
                return None

            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(RATE)
                wf.writeframes(b"".join(frames))
            return buf.getvalue()

        def recognize(wav_bytes):
            try:
                # Используем speech_recognition с аудио данными напрямую
                import speech_recognition as sr_lib
                r = sr_lib.Recognizer()
                audio = sr_lib.AudioData(wav_bytes, RATE, 2)
                return r.recognize_google(audio, language="ru-RU").lower()
            except Exception as e:
                return None

        self.after(0, lambda: self.add_message("navi", "Микрофон готов. Говори «Нави»!"))

        while self.voice_active:
            try:
                wav = record_phrase()
                if not wav:
                    continue

                text = recognize(wav)
                if not text:
                    continue

                self.after(0, lambda t=text: self.status_label.configure(
                    text=f"🎤 {t[:30]}", text_color="#4488ff"))

                triggered = any(w in text for w in wake_words)
                # Google часто сам убирает "нави" из текста
                # поэтому выполняем команду в любом случае
                if triggered:
                    cmd = text
                    for w in wake_words:
                        cmd = cmd.replace(w, "").strip(" ,.")
                    cmd = cmd.strip()
                else:
                    cmd = text.strip()

                if cmd:
                    self.after(0, lambda c=cmd: self.send_message(voice_text=c))
            except Exception:
                pass

    # ── FILES ──
    def attach_file(self):
        from tkinter import filedialog
        files = filedialog.askopenfilenames(
            title="Выбери файл",
            filetypes=[
                ("Изображения", "*.png *.jpg *.jpeg *.gif *.webp"),
                ("Текстовые", "*.txt *.md *.csv *.html *.py *.js"),
                ("Все файлы", "*.*")
            ]
        )
        if not files:
            return
        names = []
        for path in files:
            if os.path.getsize(path) > 50 * 1024 * 1024:
                self.add_message("sys", f"Файл слишком большой (макс 50MB)")
                continue
            ext = path.lower().split(".")[-1]
            if ext in ["png", "jpg", "jpeg", "gif", "webp"]:
                with open(path, "rb") as f:
                    data = base64.b64encode(f.read()).decode()
                mime = "image/jpeg" if ext == "jpg" else f"image/{ext}"
                self.pending_files.append({"type": "image", "name": os.path.basename(path), "data": data, "mime": mime})
            else:
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        data = f.read()
                    self.pending_files.append({"type": "file", "name": os.path.basename(path), "data": data})
                except:
                    self.add_message("sys", f"Не удалось прочитать файл")
                    continue
            names.append(os.path.basename(path))

        if names:
            self.files_label.configure(text="📎 " + ", ".join(names))
            self.files_label.pack(before=self.chat_area.winfo_children()[-1], padx=16, pady=(0, 4), anchor="w")


if __name__ == "__main__":
    app = NaviApp()
    app.mainloop()
