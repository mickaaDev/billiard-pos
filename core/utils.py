from escpos.printer import Network

def print_receipt_58mm(session, items, grand_total, finish_time, duration_min):
    try:
        p = Network('172.17.0.1')
        p.charcode('PC866') 
        
        p.set(align='center', text_type='B', width=2, height=2)
        p.text("БИЛЬЯРДНЫЙ КЛУБ\n")
        
        p.set(align='center', text_type='NORMAL')
        if not session.end_time:
            p.text("--- ПРЕДВАРИТЕЛЬНЫЙ СЧЕТ ---\n")
        
        p.text(f"Чек №{session.id}\n")
        p.text("-" * 32 + "\n")

        # Блок времени
        p.set(align='left')
        p.text(f"Стол:    {session.resource.name}\n")
        p.text(f"Начало:  {session.start_time.strftime('%H:%M (%d.%m)')}\n")
        p.text(f"Конец:   {finish_time.strftime('%H:%M (%d.%m)')}\n")
        p.text(f"Итого:   {duration_min} мин.\n")
        p.text("-" * 32 + "\n")

        # Товары
        for item in items:
            t_price = item.total_price() if callable(item.total_price) else item.total_price
            name = item.product.name[:20]
            p.text(f"{name:<22}{int(t_price):>10}\n")

        # Итог
        p.text("-" * 32 + "\n")
        p.set(align='right', text_type='B', width=2, height=2)
        p.text(f"ИТОГО: {grand_total} сом\n")
        
        p.set(align='center', text_type='NORMAL', width=1, height=1)
        p.text("\nБлагодарим за визит!\n\n\n")
        p.cut()
        
    except Exception as e:
        print(f"Ошибка печати: {e}")