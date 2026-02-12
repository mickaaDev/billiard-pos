from escpos.printer import Network
import traceback

def print_receipt_58mm(session, items, grand_total, finish_time, duration_min):
    """
    Функция печати чека через сетевой мост на Windows.
    Ожидает, что на Windows запущен RawBT или PowerShell скрипт на порту 9100.
    """
    p = None
    try:
        print(f"LOG: Попытка подключения к принтеру host.docker.internal:9100...")
        
        # Подключаемся к Windows хосту. Timeout 5 секунд, чтобы не ждать вечно
        p = Network('host.docker.internal', port=9100, timeout=5)
        
        # Настройка кодировки (Xprinter обычно использует CP866 или PC866)
        try:
            p.charcode('CP866')
        except Exception as e:
            print(f"LOG: Ошибка установки кодировки (пропускаем): {e}")

        # --- Заголовок чека ---
        p.set(align='center', bold=True, width=2, height=2)
        p.text("БИЛЬЯРДНЫЙ КЛУБ\n")
        
        p.set(align='center', bold=False, width=1, height=1)
        if not session.end_time:
            p.text("--- ПРЕДЧЕК ---\n")
        
        p.text(f"Чек N {session.id}\n")
        p.text("-" * 32 + "\n")

        # --- Детали сессии ---
        p.set(align='left')
        p.text(f"Стол:   {session.resource.name}\n")
        p.text(f"Начало: {session.start_time.strftime('%H:%M (%d.%m)')}\n")
        if finish_time:
            p.text(f"Конец:  {finish_time.strftime('%H:%M (%d.%m)')}\n")
        p.text(f"Время:  {duration_min} мин.\n")
        p.text("-" * 32 + "\n")

        # --- Товары и услуги ---
        for item in items:
            t_price = item.total_price() if callable(item.total_price) else item.total_price
            name = item.product.name[:20]
            price_str = f"{int(t_price):>10}"
            p.text(f"{name:<22}{price_str}\n")
            if item.quantity > 1:
                p.text(f"  Кол-во: {item.quantity}\n")

        # --- Итог ---
        p.text("-" * 32 + "\n")
        p.set(align='right', bold=True, width=2, height=2)
        p.text(f"ИТОГО:{grand_total} сом\n")
        
        # --- Подвал ---
        p.set(align='center', bold=False, width=1, height=1)
        p.text("\nБлагодарим за визит!\n")
        p.text(finish_time.strftime('%d.%m.%Y %H:%M') + "\n")
        p.text("\n\n\n")
        
        # Команда отреза (или прокрутки)
        p.cut()
        print("LOG: Данные успешно отправлены на принтер.")

    except Exception as e:
        print("--- КРИТИЧЕСКАЯ ОШИБКА ПЕЧАТИ ---")
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Описание: {e}")
        # Выводит полный путь ошибки, чтобы понять, это таймаут или отказ в соединении
        traceback.print_exc() 
        print("---------------------------------")
    
    finally:
        # Пытаемся закрыть соединение, если оно было открыто
        if p:
            try:
                p.close()
            except:
                pass