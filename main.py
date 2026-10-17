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
from datetime import datetime

import flet as ft

SCHOOL = "مدرسة ميسلون - الحلقة الثانية"
CREDIT = "برمجة المهندس مهند النابلسي بلغة Python"
EVALS = ["ممتاز", "جيد جداً", "جيد", "مقبول", "ضعيف"]
HEAD = ["الاسم", "الصف", "الشعبة", "التقييم", "الغياب", "النشاط"]

DATA_DIR = os.environ.get("FLET_APP_STORAGE_DATA") or os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "school.db")
OUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Maysaloun")


def connect():
    con = sqlite3.connect(DB_FILE, check_same_thread=False)
    con.execute("""CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, grade TEXT, section TEXT,
        evaluation TEXT, absence INTEGER DEFAULT 0, activity TEXT)""")
    con.commit()
    return con


def cell(x):
    return str(x).replace("\t", " ").replace("\n", " ")


def main(page: ft.Page):
    page.title = SCHOOL
    page.rtl = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    con = connect()
    st = {"q": "", "f": "all"}
    R = ft.TextAlign.RIGHT
    mobile = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)

    def toast(msg):
        page.open(ft.SnackBar(ft.Text(msg)))

    def confirm(title, text, on_yes):
        def yes(e):
            page.close(dlg)
            on_yes()
        dlg = ft.AlertDialog(
            title=ft.Text(title), content=ft.Text(text),
            actions=[ft.TextButton("إلغاء", on_click=lambda e: page.close(dlg)),
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
            "SELECT id,name,grade,section,evaluation,absence,activity FROM students "
            + sql + " ORDER BY grade,section,name", args).fetchall()

    def tile(r):
        sid, name, g, s, ev, ab, _ = r
        color = ft.Colors.GREEN_700 if ab == 0 else (ft.Colors.ORANGE_800 if ab < 3 else ft.Colors.RED_700)
        return ft.ListTile(
            title=ft.Text(name),
            subtitle=ft.Text(f"{g} - {s}   |   {ev or '—'}"),
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
        r = ("", "", "", None, 0, "")
        if sid:
            r = con.execute("SELECT name,grade,section,evaluation,absence,activity FROM students WHERE id=?",
                            (sid,)).fetchone()
        f_name = ft.TextField(label="اسم الطالب", value=r[0], text_align=R)
        f_grade = ft.TextField(label="الصف", value=r[1] or "", text_align=R, width=140)
        f_sec = ft.TextField(label="الشعبة", value=r[2] or "", text_align=R, width=140)
        f_ev = ft.Dropdown(label="التقييم", value=r[3] or None, width=300,
                           options=[ft.dropdown.Option(x) for x in EVALS])
        n = {"v": r[4] or 0}
        ab = ft.Text(str(n["v"]), size=20, weight=ft.FontWeight.BOLD)
        f_act = ft.TextField(label="النشاط", value=r[5] or "", multiline=True,
                             min_lines=2, max_lines=5, text_align=R)

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
                    f_ev.value or "", n["v"], f_act.value.strip()]
            if sid:
                con.execute("UPDATE students SET name=?,grade=?,section=?,evaluation=?,"
                            "absence=?,activity=? WHERE id=?", vals + [sid])
            else:
                con.execute("INSERT INTO students(name,grade,section,evaluation,absence,activity) "
                            "VALUES(?,?,?,?,?,?)", vals)
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
        dlg = ft.AlertDialog(
            title=ft.Text("تعديل بيانات طالب" if sid else "إضافة طالب"),
            content=ft.Column([
                f_name, ft.Row([f_grade, f_sec]), f_ev,
                ft.Row([ft.Text("الغياب (أيام):"),
                        ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, on_click=lambda e: step(-1)),
                        ab,
                        ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, on_click=lambda e: step(1))]),
                f_act], tight=True, scroll=ft.ScrollMode.AUTO, width=300),
            actions=actions)
        page.open(dlg)

    def import_dialog(e=None):
        box = ft.TextField(multiline=True, min_lines=6, max_lines=10, text_align=R,
                           hint_text="أحمد علي, السابع, أ\nسعاد محمد, السابع, ب")

        def do(e):
            n = 0
            for line in (box.value or "").splitlines():
                c = [x.strip() for x in re.split(r"[\t,;،]", line)]
                if not c[0] or c[0] in ("الاسم", "name"):
                    continue
                con.execute("INSERT INTO students(name,grade,section) VALUES(?,?,?)",
                            (c + ["", ""])[:3])
                n += 1
            con.commit()
            page.close(dlg)
            refresh()
            toast(f"تمت إضافة {n} طالب")

        dlg = ft.AlertDialog(
            title=ft.Text("استيراد طلاب"),
            content=ft.Column([ft.Text("الصق القائمة: سطر لكل طالب (الاسم، الصف، الشعبة) "
                                       "- يمكن نسخها من Excel.", size=12), box],
                              tight=True, scroll=ft.ScrollMode.AUTO, width=300),
            actions=[ft.TextButton("إلغاء", on_click=lambda e: page.close(dlg)),
                     ft.ElevatedButton("استيراد", on_click=do)])
        page.open(dlg)

    # ---------------------------------------------------------- Excel والطباعة
    def export_rows():
        return [[r[1], r[2], r[3], r[4] or "", r[5], r[6] or ""] for r in fetch()]

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
    flt = ft.Dropdown(width=330, value="all", options=[ft.dropdown.Option("all", "كل الصفوف والشعب")],
                      on_change=on_filter)
    search = ft.TextField(hint_text="بحث بالاسم أو الصف أو الشعبة", prefix_icon=ft.Icons.SEARCH,
                          dense=True, text_align=R, on_change=on_search)
    top = ft.Column([
        ft.Row([ft.ElevatedButton("إضافة طالب", icon=ft.Icons.PERSON_ADD, on_click=lambda e: student_dialog()),
                ft.OutlinedButton("استيراد", icon=ft.Icons.UPLOAD, on_click=import_dialog)], wrap=True),
        ft.Row([ft.FilledTonalButton("Excel", icon=ft.Icons.TABLE_CHART, on_click=to_excel),
                ft.FilledTonalButton("طباعة", icon=ft.Icons.PRINT, on_click=to_print)], wrap=True),
        flt, search, count], spacing=6)
    footer = ft.Container(ft.Text(CREDIT, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_900),
                          alignment=ft.alignment.center, padding=6)

    page.appbar = ft.AppBar(title=ft.Text(SCHOOL), center_title=True,
                            bgcolor=ft.Colors.TEAL_700, color=ft.Colors.WHITE)
    page.add(ft.SafeArea(content=ft.Column([
        ft.Container(top, padding=8),
        ft.Container(lv, expand=True, padding=ft.padding.symmetric(horizontal=8)),
        footer], expand=True, spacing=0), expand=True))
    refresh()


ft.app(target=main)
