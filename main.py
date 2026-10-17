# -*- coding: utf-8 -*-
"""
نظام متابعة الطلاب - مدرسة ميسلون (الحلقة الثانية)
تجربة على الكمبيوتر:  flet run main.py
بناء أندرويد:          flet build apk
"""
import csv
import html
import os
import re
import sqlite3
import webbrowser
from datetime import datetime, timedelta

import flet as ft

SCHOOL = "مدرسة ميسلون - الحلقة الثانية"
CREDIT = "برمجة المهندس مهند النابلسي بلغة Python"
EVALS = ["ممتاز", "جيد جداً", "جيد", "مقبول", "ضعيف"]
HEAD = ["الاسم", "الصف", "الشعبة", "التاريخ", "التقييم", "الغياب", "النشاط"]

DATA_DIR = os.environ.get("FLET_APP_STORAGE_DATA") or os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "school.db")
OUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Maysaloun")


def connect():
    con = sqlite3.connect(DB_FILE, check_same_thread=False)
    con.execute("""CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, grade TEXT, section TEXT,
        evaluation TEXT, absence INTEGER DEFAULT 0, activity TEXT, rec_date TEXT)""")
    # ترقية قاعدة بيانات قديمة لا تحتوي عمود التاريخ
    if "rec_date" not in [r[1] for r in con.execute("PRAGMA table_info(students)")]:
        con.execute("ALTER TABLE students ADD COLUMN rec_date TEXT")
    con.commit()
    return con


def cell(x):
    return str(x).replace("\t", " ").replace("\n", " ")


def main(page: ft.Page):
    page.title = SCHOOL
    page.rtl = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    try:
        page.locale_configuration = ft.LocaleConfiguration(
            supported_locales=[ft.Locale("ar", "SA")], current_locale=ft.Locale("ar", "SA"))
    except Exception:
        pass
    con = connect()
    st = {"q": "", "f": "all"}
    R = ft.TextAlign.RIGHT
    mobile = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)

    def toast(msg):
        page.open(ft.SnackBar(ft.Text(msg)))

    def dlg_w():
        # عرض المحتوى يتكيف مع عرض الشاشة حتى لا يخرج أي مربع عن الإطار
        return int(max(240, min((page.width or 360) - 96, 360)))

    def tf(label, **kw):
        return ft.TextField(label=label, dense=True, text_size=13, text_align=R,
                            label_style=ft.TextStyle(size=12),
                            content_padding=ft.padding.symmetric(horizontal=10, vertical=8), **kw)

    def make_dialog(title, content, actions):
        return ft.AlertDialog(
            title=ft.Text(title, size=16), content=content, actions=actions,
            inset_padding=ft.padding.symmetric(horizontal=16, vertical=24),
            title_padding=ft.padding.only(left=16, right=16, top=14, bottom=4),
            content_padding=ft.padding.symmetric(horizontal=16, vertical=8),
            actions_padding=ft.padding.symmetric(horizontal=12, vertical=8))

    def confirm(title, text, on_yes):
        def yes(e):
            page.close(dlg)
            on_yes()
        dlg = make_dialog(title, ft.Text(text, size=13),
                          [ft.TextButton("إلغاء", on_click=lambda e: page.close(dlg)),
                           ft.ElevatedButton("تأكيد", on_click=yes)])
        page.open(dlg)

    # ---------------------------------------------------------- البيانات
    def fetch():
        sql = "WHERE (name LIKE ? OR grade LIKE ? OR section LIKE ?)"
        args = [f"%{st['q']}%"] * 3
        if st["f"] != "all":
            g, s = st["f"].split("|", 1)
            sql += " AND grade=? AND section=?"
            args += [g, s]
        return con.execute(
            "SELECT id,name,grade,section,evaluation,absence,activity,rec_date FROM students "
            + sql + " ORDER BY grade,section,name", args).fetchall()

    def tile(r):
        sid, name, g, s, ev, ab, _, d = r
        color = ft.Colors.GREEN_700 if ab == 0 else (ft.Colors.ORANGE_800 if ab < 3 else ft.Colors.RED_700)
        sub = f"{g} - {s}   |   {ev or '—'}" + (f"\n{d}" if d else "")
        return ft.ListTile(
            title=ft.Text(name),
            subtitle=ft.Text(sub, size=12),
            trailing=ft.Container(ft.Text(f"غياب {ab}", color=ft.Colors.WHITE, size=12),
                                  bgcolor=color, border_radius=12,
                                  padding=ft.padding.symmetric(horizontal=10, vertical=4)),
            on_click=lambda e, i=sid: student_dialog(i))

    def refresh():
        combos = con.execute("SELECT DISTINCT grade, section FROM students ORDER BY grade, section").fetchall()
        flt.options = [ft.dropdown.Option("all", "كل الصفوف والشعب")] + [
            ft.dropdown.Option(f"{g}|{s}", f"{g} - {s}") for g, s in combos]
        if st["f"] not in [o.key for o in flt.options]:
            st["f"] = "all"
        flt.value = st["f"]
        rows = fetch()
        lv.controls = [tile(r) for r in rows]
        count.value = f"عدد الطلاب: {len(rows)}"
        page.update()

    # ---------------------------------------------------------- نافذة الطالب
    def student_dialog(sid=None):
        w = dlg_w()
        half = (w - 8) // 2
        r = ("", "", "", None, 0, "", datetime.now().strftime("%Y-%m-%d"))
        if sid:
            r = con.execute("SELECT name,grade,section,evaluation,absence,activity,rec_date "
                            "FROM students WHERE id=?", (sid,)).fetchone()

        def pick_date(e):
            try:
                cur = datetime.strptime(f_date.value, "%Y-%m-%d")
            except ValueError:
                cur = datetime.now()

            def chosen(ev):
                # +12 ساعة تعالج فرق التوقيت فيبقى اليوم المختار هو نفسه
                v = ev.control.value.replace(tzinfo=None) + timedelta(hours=12)
                f_date.value = v.strftime("%Y-%m-%d")
                f_date.update()
            page.open(ft.DatePicker(value=cur, first_date=datetime(2020, 1, 1),
                                    last_date=datetime(2040, 12, 31), on_change=chosen))

        f_name = tf("اسم الطالب", value=r[0], width=w)
        f_grade = tf("الصف", value=r[1] or "", width=half)
        f_sec = tf("الشعبة", value=r[2] or "", width=half)
        f_date = tf("التاريخ", value=r[6] or "", width=w, read_only=True,
                    suffix=ft.IconButton(ft.Icons.CALENDAR_MONTH, icon_size=20, on_click=pick_date))
        f_ev = ft.Dropdown(label="التقييم", value=r[3] or None, width=w, dense=True, text_size=13,
                           label_style=ft.TextStyle(size=12),
                           options=[ft.dropdown.Option(x) for x in EVALS])
        f_act = tf("النشاط", value=r[5] or "", width=w, multiline=True, min_lines=2, max_lines=4)
        n = {"v": r[4] or 0}
        ab = ft.Text(str(n["v"]), size=18, weight=ft.FontWeight.BOLD)

        def step(d):
            n["v"] = max(0, n["v"] + d)
            ab.value = str(n["v"])
            ab.update()

        def save(e):
            if not f_name.value.strip():
                f_name.error_text = "مطلوب"
                dlg.update()
                return
            vals = [f_name.value.strip(), f_grade.value.strip(), f_sec.value.strip(),
                    f_ev.value or "", n["v"], f_act.value.strip(), f_date.value or ""]
            if sid:
                con.execute("UPDATE students SET name=?,grade=?,section=?,evaluation=?,"
                            "absence=?,activity=?,rec_date=? WHERE id=?", vals + [sid])
            else:
                con.execute("INSERT INTO students(name,grade,section,evaluation,absence,activity,rec_date) "
                            "VALUES(?,?,?,?,?,?,?)", vals)
            con.commit()
            page.close(dlg)
            refresh()

        def delete(e):
            page.close(dlg)

            def do():
                con.execute("DELETE FROM students WHERE id=?", (sid,))
                con.commit()
                refresh()
            confirm("حذف الطالب", "سيتم حذف الطالب وكل بياناته. متأكد؟", do)

        actions = []
        if sid:
            actions.append(ft.TextButton("حذف", on_click=delete,
                                         style=ft.ButtonStyle(color=ft.Colors.RED_700)))
        actions += [ft.TextButton("إلغاء", on_click=lambda e: page.close(dlg)),
                    ft.ElevatedButton("حفظ", on_click=save)]
        absence_row = ft.Row(
            [ft.Text("الغياب (أيام):", size=13),
             ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_size=22, on_click=lambda e: step(-1)),
             ab,
             ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, icon_size=22, on_click=lambda e: step(1))],
            spacing=4, width=w)
        dlg = make_dialog(
            "تعديل بيانات طالب" if sid else "إضافة طالب",
            ft.Column([f_name, ft.Row([f_grade, f_sec], spacing=8, width=w), f_date, f_ev,
                       absence_row, f_act],
                      tight=True, spacing=8, scroll=ft.ScrollMode.AUTO, width=w),
            actions)
        page.open(dlg)

    def import_dialog(e=None):
        w = dlg_w()
        box = tf("القائمة", width=w, multiline=True, min_lines=5, max_lines=8,
                 hint_text="أحمد علي, السابع, أ\nسعاد محمد, السابع, ب")

        def do(e):
            n = 0
            today = datetime.now().strftime("%Y-%m-%d")
            for line in (box.value or "").splitlines():
                c = [x.strip() for x in re.split(r"[\t,;،]", line)]
                if not c[0] or c[0] in ("الاسم", "name"):
                    continue
                con.execute("INSERT INTO students(name,grade,section,rec_date) VALUES(?,?,?,?)",
                            ((c + ["", ""])[:3]) + [today])
                n += 1
            con.commit()
            page.close(dlg)
            refresh()
            toast(f"تمت إضافة {n} طالب")

        dlg = make_dialog(
            "استيراد طلاب",
            ft.Column([ft.Text("الصق القائمة: سطر لكل طالب (الاسم، الصف، الشعبة) "
                               "- يمكن نسخها من Excel.", size=12), box],
                      tight=True, spacing=8, scroll=ft.ScrollMode.AUTO, width=w),
            [ft.TextButton("إلغاء", on_click=lambda e: page.close(dlg)),
             ft.ElevatedButton("استيراد", on_click=do)])
        page.open(dlg)

    # ---------------------------------------------------------- Excel والطباعة
    def export_rows():
        return [[r[1], r[2], r[3], r[7] or "", r[4] or "", r[5], r[6] or ""] for r in fetch()]

    def out_path(ext):
        os.makedirs(OUT_DIR, exist_ok=True)
        return os.path.join(OUT_DIR, f"students_{datetime.now():%Y%m%d_%H%M%S}.{ext}")

    def open_file(p):
        if hasattr(os, "startfile"):
            os.startfile(p)
        else:
            webbrowser.open("file://" + p)

    def to_excel(e):
        rows = export_rows()
        if mobile:
            lines = ["\t".join(HEAD)] + ["\t".join(cell(x) for x in r) for r in rows] + ["", CREDIT]
            page.set_clipboard("\n".join(lines))
            toast("تم النسخ - الصقه في Excel أو Google Sheets")
            return
        p = out_path("csv")
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow([SCHOOL])
            w.writerow(HEAD)
            w.writerows(rows)
            w.writerow([])
            w.writerow([CREDIT])
        open_file(p)
        toast("تم الحفظ في: " + p)

    def to_print(e):
        rows = export_rows()
        if mobile:
            lines = [SCHOOL, ""] + [" | ".join(f"{h}: {cell(v)}" for h, v in zip(HEAD, r)) for r in rows]
            page.set_clipboard("\n".join(lines + ["", CREDIT]))
            toast("تم النسخ - الصقه في Word أو واتساب ثم اطبع")
            return
        th = "".join(f"<th>{h}</th>" for h in HEAD)
        tr = "".join("<tr>" + "".join(f"<td>{html.escape(str(x))}</td>" for x in r) + "</tr>"
                     for r in rows)
        doc = ('<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8">'
               f"<title>{SCHOOL}</title><style>"
               "body{font-family:Arial,Tahoma;margin:24px}h2{text-align:center}"
               "table{width:100%;border-collapse:collapse}"
               "td,th{border:1px solid #444;padding:6px;text-align:center}"
               "th{background:#e8eef7}footer{margin-top:20px;text-align:center;font-weight:bold}"
               f'</style></head><body onload="window.print()"><h2>{SCHOOL}</h2>'
               f"<table><tr>{th}</tr>{tr}</table><footer>{CREDIT}</footer></body></html>")
        p = out_path("html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(doc)
        open_file(p)

    # ---------------------------------------------------------- الواجهة
    def on_search(e):
        st["q"] = e.control.value.strip()
        refresh()

    def on_filter(e):
        st["f"] = e.control.value or "all"
        refresh()

    lv = ft.ListView(expand=True)
    count = ft.Text("", size=12)
    flt = ft.Dropdown(width=int(min(330, (page.width or 360) - 16)), value="all", dense=True, text_size=13,
                      options=[ft.dropdown.Option("all", "كل الصفوف والشعب")], on_change=on_filter)
    search = ft.TextField(hint_text="بحث بالاسم أو الصف أو الشعبة", prefix_icon=ft.Icons.SEARCH,
                          dense=True, text_size=13, text_align=R, on_change=on_search)
    top = ft.Column([
        ft.Row([ft.ElevatedButton("إضافة طالب", icon=ft.Icons.PERSON_ADD, on_click=lambda e: student_dialog()),
                ft.OutlinedButton("استيراد", icon=ft.Icons.UPLOAD, on_click=import_dialog)], wrap=True),
        ft.Row([ft.FilledTonalButton("Excel", icon=ft.Icons.TABLE_CHART, on_click=to_excel),
                ft.FilledTonalButton("طباعة", icon=ft.Icons.PRINT, on_click=to_print)], wrap=True),
        flt, search, count], spacing=6)
    footer = ft.Container(ft.Text(CREDIT, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_900),
                          alignment=ft.alignment.center, padding=6)

    page.appbar = ft.AppBar(title=ft.Text(SCHOOL, size=18), center_title=True,
                            bgcolor=ft.Colors.TEAL_700, color=ft.Colors.WHITE)
    page.add(ft.SafeArea(content=ft.Column([
        ft.Container(top, padding=8),
        ft.Container(lv, expand=True, padding=ft.padding.symmetric(horizontal=8)),
        footer], expand=True, spacing=0), expand=True))
    refresh()


ft.app(target=main)
