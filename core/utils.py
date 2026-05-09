# import win32print
# import pytz 
import traceback
from datetime import datetime
from decimal import Decimal

def print_receipt_58mm(session, items, grand_total, finish_time, duration_min):
    """
    Full printing function for Windows native Django.
    Includes Pause Duration tracking and 5-minute cap logic.
    """
    printer_name = "xprinter"
    PAUSE_LIMIT = 5 # Business rule: max 5 mins discount per pause
    
    # 1. Handle Timezone & Time Calculations
    try:
        bishkek_tz = pytz.timezone('Asia/Bishkek')
        # Ensure we have a timezone-aware start time
        if session.start_time.tzinfo is None:
            start_time_aware = pytz.utc.localize(session.start_time)
        else:
            start_time_aware = session.start_time
            
        start_time_local = start_time_aware.astimezone(bishkek_tz)
        current_time_local = datetime.now(bishkek_tz)
    except Exception as e:
        print(f"Timezone error: {e}")
        start_time_local = session.start_time
        current_time_local = datetime.now()

    # 2. Calculate Total Discounted Pause Time
    total_pause_mins = 0
    pauses = session.pauses.all()
    for pause in pauses:
        if pause.resumed_at:
            # min(actual duration, 5 mins)
            diff = (pause.resumed_at - pause.paused_at).total_seconds() / 60
            total_pause_mins += min(diff, PAUSE_LIMIT)
        elif not session.is_active:
            # If session closed while on pause
            ref_time = session.end_time if session.end_time else datetime.now()
            diff = (ref_time - pause.paused_at).total_seconds() / 60
            total_pause_mins += min(diff, PAUSE_LIMIT)

    try:
        # --- 3. Build ESC/POS Data ---
        raw_data = b'\x1b\x40' # Initialize printer
        
        # HEADER (Center Align)
        raw_data += b'\x1b\x61\x01'
        raw_data += b'\x1b\x21\x10' # Double height
        raw_data += "БИЛЬЯРДНЫЙ КЛУБ САКУРА\n".encode('cp866')
        raw_data += b'\x1b\x21\x00' # Back to normal text
        raw_data += f"Чек №{session.id}\n".encode('cp866')
        raw_data += (("-" * 30) + "\n").encode('cp866')
        
        # SESSION INFO (Left Align)
        raw_data += b'\x1b\x61\x00'
        start_str = start_time_local.strftime('%H:%M')
        if finish_time:
            # Ensure finish_time is bishkek local
            try:
                if finish_time.tzinfo is None:
                    finish_time = pytz.utc.localize(finish_time).astimezone(bishkek_tz)
                else:
                    finish_time = finish_time.astimezone(bishkek_tz)
                end_str = finish_time.strftime('%H:%M')
            except:
                end_str = current_time_local.strftime('%H:%M')
        else:
            end_str = "---"

        if session.mode == 'BAR':
            raw_data += b'\x1b\x45\x01' # Bold ON
            raw_data += "ТИП:     БАРНЫЙ СЧЕТ\n".encode('cp866')
            raw_data += b'\x1b\x45\x00' # Bold OFF
            raw_data += f"Дата:    {current_time_local.strftime('%d.%m %H:%M')}\n".encode('cp866')
        else:
            res_name = session.resource.name if session.resource else "---"
            
            raw_data += f"Стол:    {res_name}\n".encode('cp866')
            raw_data += f"Начало:  {start_str}\n".encode('cp866')
            raw_data += f"Конец:   {end_str}\n".encode('cp866') # Explicit End Time
            
            # Show pause info if it exists
            if total_pause_mins > 0:
                raw_data += f"Пауза:   {int(total_pause_mins)} мин. (скидка)\n".encode('cp866')
            
            raw_data += f"Чистое время: {duration_min} мин.\n".encode('cp866')

        # ITEMS TABLE (Products/Drinks)
        for item in items:
            t_price = item.total_price() if callable(item.total_price) else item.total_price
            quantity = getattr(item, 'quantity', 1)
            # Truncate name to fit 58mm paper (approx 30-32 chars per line)
            name = item.product.name[:16]
            
            item_line_left = f"{name} x{quantity}"
            price_str = f"{int(t_price):>10}"
            raw_data += f"{item_line_left:<20}{price_str}\n".encode('cp866')

        raw_data += (("-" * 30) + "\n").encode('cp866')
        
        # TOTAL (Right Align + Bold)
        raw_data += b'\x1b\x61\x02'
        raw_data += b'\x1b\x45\x01' 
        raw_data += f"К ОПЛАТЕ: {int(grand_total)} СОМ\n".encode('cp866')
        raw_data += b'\x1b\x45\x00' 
        
        # FOOTER (Center Align)
        raw_data += b'\x1b\x61\x01'
        raw_data += "\nПриятного отдыха!\n".encode('cp866')
        raw_data += f"{current_time_local.strftime('%d.%m.%Y %H:%M')}\n".encode('cp866')
        
        # Paper Feed and Cut
        raw_data += b"\n\n\n\n\n"
        raw_data += b"\x1d\x56\x01" # Full cut command for Xprinter

        # --- 4. Send to Windows Spooler ---
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            job_info = (f"Bill_{session.id}", None, "RAW")
            win32print.StartDocPrinter(hPrinter, 1, job_info)
            win32print.StartPagePrinter(hPrinter)
            win32print.WritePrinter(hPrinter, raw_data)
            win32print.EndPagePrinter(hPrinter)
            win32print.EndDocPrinter(hPrinter)
        finally:
            win32print.ClosePrinter(hPrinter)

    except Exception:
        print("Printing failed:")
        traceback.print_exc()