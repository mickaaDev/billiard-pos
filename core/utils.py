import win32print
import traceback

def print_receipt_58mm(session, items, grand_total, finish_time, duration_min):
    # Укажи точное имя принтера из панели управления Windows
    printer_name = "xprinter" 
    
    try:
        # 1. Формируем сырые данные (ESC/POS команды)
        # \x1b\x40 - инициализация принтера
        # \x1b\x61\x01 - выравнивание по центру
        raw_data = b'\x1b\x40' 
        raw_data += b'\x1b\x61\x01'
        raw_data += "BILLIARD CLUB\n".encode('cp866')
        
        # Разделитель
        raw_data += b'\x1b\x61\x00' # Выравнивание по левому краю
        raw_data += ("-" * 32 + "\n").encode('cp866')
        
        # Данные сессии
        raw_data += f"Table: {session.resource.name}\n".encode('cp866')
        raw_data += f"Time:  {duration_min} min\n".encode('cp866')
        raw_data += ("-" * 32 + "\n").encode('cp866')

        # Товары
        for item in items:
            name = item.product.name[:20]
            price = f"{int(item.total_price):>10}"
            raw_data += f"{name:<22}{price}\n".encode('cp866')

        raw_data += ("-" * 32 + "\n").encode('cp866')
        raw_data += f"TOTAL: {grand_total} SOM\n".encode('cp866')
        
        # Команды прокрутки и отреза
        raw_data += b"\n\n\n\n"
        raw_data += b"\x1d\x56\x01" # Команда отреза (Paper Cut)

        # 2. Отправляем в принтер через Win32 API
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            # Создаем документ "RAW" (сырые данные)
            job_info = ("Billiard Receipt", None, "RAW")
            hJob = win32print.StartDocPrinter(hPrinter, 1, job_info)
            win32print.StartPagePrinter(hPrinter)
            win32print.WritePrinter(hPrinter, raw_data)
            win32print.EndPagePrinter(hPrinter)
            win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)
            
        print(f"LOG: Receipt sent to {printer_name} successfully.")

    except Exception as e:
        print("--- PRINT ERROR ---")
        traceback.print_exc()