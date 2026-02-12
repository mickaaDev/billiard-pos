from escpos.printer import Network 

def print_receipt_58mm(session, items, grand_total, finish_time, duration_min):
    try:
        # Подключаемся к принтеру
        p = Network('172.17.0.1')

        # Пытаемся установить кириллицу (CP866 чаще работает на Xprinter)
        try:
            p.charcode('CP866')
        except:
            pass

        # --- Шапка ---
        # Вместо text_type='B' используем bold=True
        p.set(align='center', bold=True, width=2, height=2)
        p.text("БИЛЬЯРДНЫЙ\nКЛУБ\n")
        
        p.set(align='center', bold=False, width=1, height=1)
        if not session.end_time:
            p.text("--- ПРЕДЧЕК ---\n")
        
        p.text(f"Чек N {session.id}\n")
        p.text("-" * 32 + "\n")

        # --- Блок времени ---
        p.set(align='left')
        p.text(f"Стол:   {session.resource.name}\n")
        p.text(f"Начало: {session.start_time.strftime('%H:%M (%d.%m)')}\n")
        if finish_time:
            p.text(f"Конец:  {finish_time.strftime('%H:%M (%d.%m)')}\n")
        p.text(f"Итого:  {duration_min} мин.\n")
        p.text("-" * 32 + "\n")

        # --- Товары ---
        for item in items:
            t_price = item.total_price() if callable(item.total_price) else item.total_price
            name = item.product.name[:20]
            price_str = f"{int(t_price):>10}"
            p.text(f"{name:<22}{price_str}\n")

        # --- Итого ---
        p.text("-" * 32 + "\n")
        # Вместо text_type='B' используем bold=True
        p.set(align='right', bold=True, width=2, height=2)
        p.text(f"ИТОГО:{grand_total} сом\n")
        
        # --- Подвал ---
        p.set(align='center', bold=False, width=1, height=1)
        p.text("\nБлагодарим за визит!\n\n\n")
        p.cut()
        
    except Exception as e:
        print(f"Ошибка печати в print_receipt_58mm: {e}")