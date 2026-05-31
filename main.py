"""
Universal Duplicate Finder (Mobile APK)
- Scans Photos, Videos, and Documents
- Permission Handling Added
- Anti-Freeze Fix for Android 16
"""

import flet as ft
import os, hashlib, threading, time, traceback

# ─── FILE EXTENSIONS ───
PHOTO_EXTS = {'.jpg','.jpeg','.png','.bmp','.webp','.heic'}
VIDEO_EXTS = {'.mp4','.mkv','.avi','.mov','.flv','.webm'}
DOC_EXTS = {'.pdf','.docx','.doc','.txt','.xlsx','.xls','.pptx','.csv'}

def file_md5(path):
    h = hashlib.md5()
    try:
        # File ko chhote chunks mein read karna (1GB ki video bhi safely scan hogi)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1048576), b""): # 1MB chunks for speed
                h.update(chunk)
    except:
        pass
    return h.hexdigest()

def fmtsz(b):
    if b < 1024:    return f"{b} B"
    if b < 1<<20:   return f"{b/1024:.1f} KB"
    if b < 1<<30:   return f"{b/1048576:.1f} MB"
    return f"{b/1073741824:.2f} GB"

def main(page: ft.Page):
    try:
        page.title = "Universal Duplicate Finder"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 15
        page.scroll = "adaptive"

        # ─── PERMISSION HANDLER ───
        ph = ft.PermissionHandler()
        page.overlay.append(ph)

        app_state = {
            "all_groups": [],
            "selected_files": set()
        }

        # ─── UI ELEMENTS ───
        folder_path = ft.TextField(label="Folder path", expand=True, read_only=True, border_color=ft.colors.BLUE_400)
        
        # Naye Checkboxes
        scan_photos = ft.Checkbox(label="Photos", value=True)
        scan_videos = ft.Checkbox(label="Videos", value=False)
        scan_docs = ft.Checkbox(label="Docs", value=False)
        
        prog_bar = ft.ProgressBar(value=0, color=ft.colors.AMBER_400)
        status_text = ft.Text("Ready to scan...", color=ft.colors.GREY_400, size=12)
        stats_text = ft.Text("Selected: 0 | Saved: 0 MB", color=ft.colors.CYAN_400, weight="bold")

        results_col = ft.Column(spacing=10, expand=True)

        def update_stats():
            stats_text.value = f"Selected for Delete: {len(app_state['selected_files'])}"
            page.update()

        def render_results():
            results_col.controls.clear()
            if not app_state["all_groups"]:
                results_col.controls.append(ft.Text("🎉 No duplicates found!", color=ft.colors.GREEN_400, size=18))
                page.update()
                return

            for grp in app_state["all_groups"]:
                results_col.controls.append(ft.Text(f"⚡ Duplicate Group ({len(grp['files'])} files)", color=ft.colors.RED_400, weight="bold"))
                row = ft.Row(scroll="auto", spacing=10)
                for i, path in enumerate(grp['files']):
                    is_first = (i == 0)
                    row.controls.append(create_file_card(path, is_first))
                results_col.controls.append(ft.Container(content=row, padding=10, bgcolor="#1e1e2b", border_radius=10))
                results_col.controls.append(ft.Divider())
                
            update_stats()
            page.update()

        # ─── SMART FILE CARD (Photo/Video/Doc handling) ───
        def create_file_card(path, is_first):
            fname = os.path.basename(path)
            ext = os.path.splitext(fname)[1].lower()
            short = fname[:12] + "..." if len(fname) > 14 else fname
            
            try:
                sz = os.path.getsize(path)
                sz_txt = fmtsz(sz)
            except:
                sz_txt = "Unknown"

            badge = ft.Text("", weight="bold", size=10)
            
            # Smart Icon/Image Logic
            if ext in PHOTO_EXTS:
                preview = ft.Image(src=path, width=100, height=100, fit=ft.ImageFit.COVER, border_radius=5)
            elif ext in VIDEO_EXTS:
                preview = ft.Container(content=ft.Icon(ft.icons.VIDEO_FILE, size=50, color=ft.colors.BLUE_300), width=100, height=100, alignment=ft.alignment.center, bgcolor="#2c2c3e", border_radius=5)
            else:
                preview = ft.Container(content=ft.Icon(ft.icons.INSERT_DRIVE_FILE, size=50, color=ft.colors.ORANGE_300), width=100, height=100, alignment=ft.alignment.center, bgcolor="#2c2c3e", border_radius=5)

            card = ft.Container(
                content=ft.Column([preview, badge, ft.Text(f"{short}\n{sz_txt}", size=10, text_align="center")], alignment="center", spacing=2),
                border_radius=8,
                padding=5,
                ink=True,
            )

            def update_card_visuals():
                is_sel = path in app_state["selected_files"]
                if is_sel:
                    card.bgcolor = "#331616"
                    card.border = ft.border.all(2, ft.colors.RED_400)
                    badge.value = "☑ DELETE"
                    badge.color = ft.colors.RED_200
                else:
                    card.bgcolor = "#172b23" if is_first else ft.colors.SURFACE
                    card.border = ft.border.all(2, ft.colors.GREEN_400 if is_first else ft.colors.GREY_800)
                    badge.value = "✔ SAFE" if is_first else "☐ SAFE"
                    badge.color = ft.colors.GREEN_400 if is_first else ft.colors.WHITE
                card.update()

            def toggle(e):
                if path in app_state["selected_files"]:
                    app_state["selected_files"].remove(path)
                else:
                    app_state["selected_files"].add(path)
                update_card_visuals()
                update_stats()

            card.on_click = toggle
            update_card_visuals() 
            return card

        # ─── SCAN LOGIC ───
        def start_scan(e):
            folder = folder_path.value
            if not folder or not os.path.isdir(folder):
                page.snack_bar = ft.SnackBar(ft.Text("⚠ Please select a valid folder!"))
                page.snack_bar.open = True
                page.update()
                return
                
            # Kaunsi files scan karni hain?
            target_exts = set()
            if scan_photos.value: target_exts.update(PHOTO_EXTS)
            if scan_videos.value: target_exts.update(VIDEO_EXTS)
            if scan_docs.value: target_exts.update(DOC_EXTS)

            if not target_exts:
                page.snack_bar = ft.SnackBar(ft.Text("⚠ Please select at least one file type (Photos/Videos/Docs)!"))
                page.snack_bar.open = True
                page.update()
                return

            def worker():
                scan_btn.disabled = True
                delete_btn.disabled = True
                prog_bar.value = 0
                app_state["all_groups"].clear()
                app_state["selected_files"].clear()
                results_col.controls.clear()
                page.update()

                paths = []
                # Sub-folders humesha on rakhte hain deep scan ke liye
                walk = os.walk(folder)
                status_text.value = "Finding files..."
                page.update()

                for rd, _, files in walk:
                    for f in files:
                        if os.path.splitext(f)[1].lower() in target_exts:
                            paths.append(os.path.join(rd, f))

                total = len(paths)
                if total == 0:
                    status_text.value = "⚠ No files found for selected types!"
                    scan_btn.disabled = False
                    page.update()
                    return

                md5_map = {}
                for i, p in enumerate(paths):
                    status_text.value = f"Analyzing Hash: [{i+1}/{total}]"
                    prog_bar.value = i/total
                    page.update()
                    h = file_md5(p)
                    md5_map.setdefault(h, []).append(p)

                exact_groups = [v for v in md5_map.values() if len(v)>1]
                groups = []
                for g in exact_groups:
                    groups.append({"type": "exact", "files": g, "waste": sum(os.path.getsize(p) for p in g[1:])})

                groups.sort(key=lambda g: -g["waste"]) # Sabse jyada space khane wali files upar
                app_state["all_groups"] = groups

                for g in groups:
                    for p in g["files"][1:]:
                        app_state["selected_files"].add(p)

                status_text.value = f"✅ Scan Complete! {len(groups)} duplicate groups found."
                prog_bar.value = 1.0
                scan_btn.disabled = False
                delete_btn.disabled = False
                render_results()

            threading.Thread(target=worker, daemon=True).start()

        def confirm_delete(e):
            page.dialog.open = False
            page.update()
            done, errors = 0, 0
            for p in list(app_state["selected_files"]):
                try:
                    os.remove(p)
                    done += 1
                except:
                    errors += 1
            app_state["selected_files"].clear()
            for g in app_state["all_groups"]:
                g["files"] = [f for f in g["files"] if os.path.exists(f)]
            app_state["all_groups"] = [g for g in app_state["all_groups"] if len(g["files"]) > 1]
            render_results()
            page.snack_bar = ft.SnackBar(ft.Text(f"✅ Deleted {done} files! (Errors: {errors})", color=ft.colors.GREEN))
            page.snack_bar.open = True
            page.update()

        def request_delete(e):
            if not app_state["selected_files"]:
                return
            dlg = ft.AlertDialog(
                title=ft.Text("⚠ Confirm Delete"),
                content=ft.Text(f"Are you sure you want to delete {len(app_state['selected_files'])} files forever?"),
                actions=[
                    ft.TextButton("Yes, Delete", on_click=confirm_delete, icon=ft.icons.DELETE_FOREVER, icon_color=ft.colors.RED),
                    ft.TextButton("Cancel", on_click=lambda e: setattr(page.dialog, 'open', False) or page.update())
                ]
            )
            page.dialog = dlg
            dlg.open = True
            page.update()

        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.path:
                folder_path.value = e.path
                status_text.value = f"Selected: {os.path.basename(e.path)}"
                page.update() 

        file_picker = ft.FilePicker(on_result=on_dialog_result)
        page.overlay.append(file_picker)

        # ─── BUTTONS ───
        perm_btn = ft.ElevatedButton("Unlock Storage Access (If Needed)", icon=ft.icons.LOCK_OPEN, color=ft.colors.AMBER, on_click=lambda _: ph.request_permission(ft.PermissionType.STORAGE))
        browse_btn = ft.IconButton(icon=ft.icons.FOLDER_OPEN, icon_color=ft.colors.BLUE_400, icon_size=30, on_click=lambda _: file_picker.get_directory_path())
        
        scan_btn = ft.ElevatedButton(content=ft.Row([ft.Icon(ft.icons.PLAY_ARROW, color=ft.colors.WHITE), ft.Text("FIND DUPLICATES", color=ft.colors.WHITE, weight="bold")], alignment=ft.MainAxisAlignment.CENTER), style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_700, shape=ft.RoundedRectangleBorder(radius=8)), height=50, on_click=start_scan)
        delete_btn = ft.ElevatedButton(content=ft.Row([ft.Icon(ft.icons.DELETE, color=ft.colors.WHITE), ft.Text("DELETE SELECTED", color=ft.colors.WHITE, weight="bold")], alignment=ft.MainAxisAlignment.CENTER), style=ft.ButtonStyle(bgcolor=ft.colors.RED_700, shape=ft.RoundedRectangleBorder(radius=8)), height=50, on_click=request_delete, disabled=True)

        button_layout = ft.Column([scan_btn, delete_btn], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        page.add(
            ft.Row([ft.Icon(ft.icons.FIND_IN_PAGE, size=30, color=ft.colors.BLUE_400), ft.Text("Mega File Scanner", size=22, weight="bold")], alignment=ft.MainAxisAlignment.CENTER),
            perm_btn, # Permission button sabse upar
            ft.Row([folder_path, browse_btn]),
            ft.Row([scan_photos, scan_videos, scan_docs], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            button_layout,
            ft.Container(height=5),
            ft.Container(content=prog_bar, width=float("inf")),
            ft.Row([status_text, stats_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            results_col
        )
    
    except Exception as e:
        error_details = traceback.format_exc()
        page.add(ft.Text("⚠ APP CRASHED!", color=ft.colors.RED_400, size=24, weight="bold"), ft.Text(error_details, color=ft.colors.RED_200, size=12, selectable=True))
        page.update()

if __name__ == "__main__":
    ft.app(target=main)
