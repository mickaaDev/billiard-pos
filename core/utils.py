def print_receipt_58mm(session, items, grand_total, finish_time, duration_min):
    """
    Печать чека на 58мм ленте.
    Параметры:
    - session: объект модели Session
    - items: QuerySet товаров сессии
    - grand_total: итоговая сумма (int/Decimal)
    - finish_time: время окончания (фиксированное или текущее)
    - duration_min: общая длительность в минутах
    """
    try:
        # Подключаемся к принтеру (через шлюз Docker на Windows хост)
        p = Network('172.17.0.1')

        # Установка кодировки для кириллицы. 
        # Если PC866 выдает ошибку, пробуем CP866 или игнорируем
        try:
            p.charcode('PC866') 
        except Exception as e:
            try:
                p.charcode('CP866')
            except:
                print(f"Предупреждение: не удалось установить кириллицу ({e})")

        # --- Шапка чека ---
        p.set(align='center', text_type='B', width=2, height=2)
        p.text("БИЛЬЯРДНЫЙ\n")
        p.text("КЛУБ\n")
        
        p.set(align='center', text_type='NORMAL', width=1, height=1)
        if not session.end_time:
            p.text("-" * 20 + "\n")
            p.text("ПРЕДВАРИТЕЛЬНЫЙ СЧЕТ\n")
            p.text("-" * 20 + "\n")
        
        p.text(f"Чек N {session.id}\n")
        p.text("-" * 32 + "\n")

        # --- Информация о времени ---
        p.set(align='left')
        p.text(f"Стол:   {session.resource.name}\n")
        p.text(f"Начало: {session.start_time.strftime('%H:%M (%d.%m)')}\n")
        if finish_time:
            p.text(f"Конец:  {finish_time.strftime('%H:%M (%d.%m)')}\n")
        p.text(f"Итого:  {duration_min} мин.\n")
        p.text("-" * 32 + "\n")

        # --- Список товаров/услуг ---
        # Формат: Название (20 симв) + Цена (10 симв)
        for item in items:
            # Получаем цену (проверка на метод или поле)
            t_price = item.total_price() if callable(item.total_price) else item.total_price
            
            name = item.product.name[:20]
            price_str = f"{int(t_price):>10}"
            
            p.text(f"{name:<22}{price_str}\n")
            if item.quantity > 1:
                p.text(f"  Кол-во: {item.quantity}\n")

        # --- Итоговая сумма ---
        p.text("-" * 32 + "\n")
        p.set(align='right', text_type='B', width=2, height=2)
        p.text(f"ИТОГО:{grand_total} сом\n")
        
        # --- Подвал ---
        p.set(align='center', text_type='NORMAL', width=1, height=1)
        p.text("\nБлагодарим за визит!\n")
        p.text(f"Дата: {finish_time.strftime('%d.%m.%Y %H:%M')}\n")
        p.text("\n\n") # Место для отрыва
        
        p.cut()
        
    except Exception as e:
        # Логируем ошибку в консоль Docker, чтобы не "ронять" сайт
        print(f"Ошибка печати в print_receipt_58mm: {e}")