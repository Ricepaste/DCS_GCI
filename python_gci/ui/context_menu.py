from PyQt6.QtWidgets import QMenu
from PyQt6.QtCore import Qt

def handle_radar_context_menu(radar_view, event, target_name, clicked_items):
    """
    處理 RadarView 中對航跡目標發起右鍵戰術選單的獨立控制器
    """
    if not target_name:
        return

    menu = QMenu(radar_view)
    menu.setStyleSheet("""
        QMenu {
            background-color: #121e1a;
            color: #d0e0d8;
            border: 1px solid #2e5548;
            font-family: Consolas, monospace;
            font-size: 11px;
            padding: 2px;
        }
        QMenu::item {
            padding: 4px 16px 4px 8px;
        }
        QMenu::item:selected {
            background-color: #244238;
            color: #55ff99;
        }
        QMenu::separator {
            height: 1px;
            background: #2e5548;
            margin: 3px 0px;
        }
    """)
    
    act_fnd = menu.addAction("[F] FRIENDLY")
    act_unk = menu.addAction("[U] UNKNOWN")
    act_bnd = menu.addAction("[B] BANDIT")
    act_hst = menu.addAction("[H] HOSTILE")
    menu.addSeparator()
    
    is_checked = target_name in radar_view.checked_in_tracks
    act_check = menu.addAction("[C] UNMARK" if is_checked else "[C] MARK (CHECK-IN)")
    act_vec = menu.addAction("[V] VECTOR AI...")
    act_attack = menu.addAction("[A] ATTACK TARGET...")
    
    menu_roe = menu.addMenu("ROE CONTROL")
    act_roe_des = menu_roe.addAction("DESIGNATED TARGET")
    act_roe_free = menu_roe.addAction("WEAPONS FREE")
    act_roe_hold = menu_roe.addAction("WEAPONS HOLD")
    act_roe_ret = menu_roe.addAction("RETURN FIRE")
    
    action = menu.exec(event.globalPos())
    grp_name = radar_view.track_items.get(target_name, {}).get('group_name') or target_name
    
    track_item_info = radar_view.track_items.get(target_name, {})
    is_hostile_track = track_item_info.get('is_hostile', False)
    is_friendly = not is_hostile_track
    
    targets_to_declare = list(radar_view.ordered_selection) if (target_name in radar_view.ordered_selection and len(radar_view.ordered_selection) > 0) else [target_name]
    
    if action == act_fnd:
        for t_name in targets_to_declare:
            radar_view.set_track_classification(t_name, "FRIENDLY")
    elif action == act_unk:
        for t_name in targets_to_declare:
            radar_view.set_track_classification(t_name, "UNKNOWN")
    elif action == act_bnd:
        for t_name in targets_to_declare:
            radar_view.set_track_classification(t_name, "BANDIT")
    elif action == act_hst:
        for t_name in targets_to_declare:
            radar_view.set_track_classification(t_name, "HOSTILE")
    elif action == act_check:
        if is_checked:
            radar_view.checked_in_tracks.remove(target_name)
        else:
            radar_view.checked_in_tracks.add(target_name)
        radar_view.update_tracks()
    elif action == act_vec:
        if is_friendly:
            from ui.panels import VectorParamsDialog
            curr_alt_ft = 20000
            curr_spd_kts = 350
            track_info = radar_view.track_items.get(target_name, {})
            # 如果能獲取當前數據，預載為當前高度/速度
            all_tracks = radar_view.backend.get_tracks()
            for f in all_tracks.get('friendlies', []):
                if f.get('unit_name') == target_name:
                    curr_alt_ft = int((f.get('y', 0) * 3.28084))
                    curr_spd_kts = int(geometry.calculate_speed(f.get('vx', 0), f.get('vz', 0)))
                    break
            
            dlg = VectorParamsDialog(curr_alt_ft, curr_spd_kts, radar_view)
            if dlg.exec():
                alt_ft, spd_kts = dlg.get_values()
                radar_view._vector_target_group = grp_name
                radar_view._vector_target_alt_m = alt_ft * 0.3048
                radar_view._vector_target_speed_mps = spd_kts * 0.514444
                radar_view._is_vectoring_ai = True
                
                from PyQt6.QtWidgets import QApplication
                QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
                radar_view.setCursor(Qt.CursorShape.CrossCursor)
                radar_view.viewport().setCursor(Qt.CursorShape.CrossCursor)
                if hasattr(radar_view, 'main_window'):
                    radar_view.main_window.statusBar().showMessage(f"VECTORING '{grp_name}' (FL{alt_ft//100:03d} / {spd_kts}kts): Click map destination.")
        else:
            if hasattr(radar_view, 'main_window'):
                radar_view.main_window.statusBar().showMessage(f"COMMAND REFUSED: Cannot vector non-friendly track '{target_name}'.")
    elif action == act_attack:
        if is_friendly:
            radar_view._attack_attacker_group = grp_name
            radar_view._is_selecting_attack_target = True
            from PyQt6.QtWidgets import QApplication
            QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
            radar_view.setCursor(Qt.CursorShape.CrossCursor)
            radar_view.viewport().setCursor(Qt.CursorShape.CrossCursor)
            if hasattr(radar_view, 'main_window'):
                radar_view.main_window.statusBar().showMessage(f"ATTACK ORDER [{grp_name}]: Click target track to engage.")
        else:
            if hasattr(radar_view, 'main_window'):
                radar_view.main_window.statusBar().showMessage(f"COMMAND REFUSED: Cannot order non-friendly track '{target_name}' to attack.")
    elif action == act_roe_des:
        if is_friendly:
            radar_view.backend.send_command({"action": "set_roe", "group_name": grp_name, "roe_mode": "DESIGNATED_TARGET"})
            if hasattr(radar_view, 'main_window'): radar_view.main_window.statusBar().showMessage(f"ROE [{grp_name}]: DESIGNATED TARGET.")
        else:
            if hasattr(radar_view, 'main_window'): radar_view.main_window.statusBar().showMessage(f"COMMAND REFUSED: Cannot set ROE on non-friendly track '{target_name}'.")
    elif action == act_roe_free:
        if is_friendly:
            radar_view.backend.send_command({"action": "set_roe", "group_name": grp_name, "roe_mode": "WEAPON_FREE"})
            if hasattr(radar_view, 'main_window'): radar_view.main_window.statusBar().showMessage(f"ROE [{grp_name}]: WEAPONS FREE.")
        else:
            if hasattr(radar_view, 'main_window'): radar_view.main_window.statusBar().showMessage(f"COMMAND REFUSED: Cannot set ROE on non-friendly track '{target_name}'.")
    elif action == act_roe_hold:
        if is_friendly:
            radar_view.backend.send_command({"action": "set_roe", "group_name": grp_name, "roe_mode": "WEAPON_HOLD"})
            if hasattr(radar_view, 'main_window'): radar_view.main_window.statusBar().showMessage(f"ROE [{grp_name}]: WEAPONS HOLD.")
        else:
            if hasattr(radar_view, 'main_window'): radar_view.main_window.statusBar().showMessage(f"COMMAND REFUSED: Cannot set ROE on non-friendly track '{target_name}'.")
    elif action == act_roe_ret:
        if is_friendly:
            radar_view.backend.send_command({"action": "set_roe", "group_name": grp_name, "roe_mode": "RETURN_FIRE"})
            if hasattr(radar_view, 'main_window'): radar_view.main_window.statusBar().showMessage(f"ROE [{grp_name}]: RETURN FIRE.")
        else:
            if hasattr(radar_view, 'main_window'): radar_view.main_window.statusBar().showMessage(f"COMMAND REFUSED: Cannot set ROE on non-friendly track '{target_name}'.")
        
    if hasattr(radar_view, 'status_panel') and radar_view.status_panel.isVisible():
        radar_view.refresh_status_panel()
