from escpos.printer import Network 

def print_receipt_58mm(session, items, grand_total, finish_time, duration_min):
    raise Exception("DJANGO READS THIS FILE")
    try:
        # Обращаемся к Windows-хосту из Docker
        p = Network('host.docker.internal', port=9100)

        # Кодировка для кириллицы
        try:
            p.charcode('PC866')
        except:
            pass

        p.set(align='center', bold=True, width=2, height=2)
        p.text("БИЛЬЯРДНЫЙ КЛУБ\n")
        
        p.set(align='left', bold=False, width=1, height=1)
        p.text("-" * 32 + "\n")
        p.text(f"Стол: {session.resource.name}\n")
        p.text(f"Начало: {session.start_time.strftime('%H:%M')}\n")
        p.text(f"Итого: {duration_min} мин.\n")
        p.text("-" * 32 + "\n")

        for item in items:
            t_price = item.total_price() if callable(item.total_price) else item.total_price
            name = item.product.name[:20]
            price_str = f"{int(t_price):>10}"
            p.text(f"{name:<22}{price_str}\n")

        p.text("-" * 32 + "\n")
        p.set(align='right', bold=True, width=2, height=2)
        p.text(f"ИТОГО:{grand_total} сом\n")
        p.cut()
        
    except Exception as e:
        import traceback
        print("--- ОШИБКА ПЕЧАТИ ---")
        print(traceback.format_exc())