import win32print
import traceback
from datetime import datetime
import pytz


def print_receipt_58mm(session, items, grand_total, finish_time, duration_min):
   """
   Full printing function for Windows native Django.
   Only prints 'End Time' and 'Date' if the session is closed.
   """
   printer_name = "xprinter"
  
   # 1. Handle Timezone (Bishkek, KG is UTC+6)
   try:
       bishkek_tz = pytz.timezone('Asia/Bishkek')
       start_time_local = session.start_time.astimezone(bishkek_tz)
       current_time_local = datetime.now(bishkek_tz)
   except Exception as e:
       print(f"Timezone error: {e}")
       start_time_local = session.start_time
       current_time_local = datetime.now()


   try:
       # --- 2. Build ESC/POS Data ---
       raw_data = b'\x1b\x40' # Initialize
      
       # HEADER (Center Align)
       raw_data += b'\x1b\x61\x01'
       raw_data += b'\x1b\x21\x10' # Double height
       raw_data += "БИЛЬЯРДНЫЙ КЛУБ САКУРА\n".encode('cp866')
       raw_data += b'\x1b\x21\x00' # Normal text
       raw_data += f"Чек №{session.id}\n".encode('cp866')
       raw_data += (("-" * 32) + "\n").encode('cp866')
      
       # SESSION INFO (Left Align)
       raw_data += b'\x1b\x61\x00'
       raw_data += f"Стол:    {session.resource.name}\n".encode('cp866')
       raw_data += f"Начало:  {start_time_local.strftime('%H:%M')}\n".encode('cp866')
      
       # CONDITIONAL: Only print End Time if the session is closing
       if finish_time:
           raw_data += f"Конец:   {current_time_local.strftime('%H:%M')}\n".encode('cp866')
          
       raw_data += f"Время:   {duration_min} мин.\n".encode('cp866')
       raw_data += (("-" * 32) + "\n").encode('cp866')


       # ITEMS TABLE
       for item in items:
           # Get values safely
           t_price = item.total_price() if callable(item.total_price) else item.total_price
           quantity = getattr(item, 'quantity', 1) # Fallback to 1 if quantity isn't an attribute
           name = item.product.name[:18] # Shorten name slightly to make room for qty
          
           # Format: "Product x Qty" on the left, "Price" on the right
           # Example: "Cola x 2            500"
           item_line_left = f"{name} x {quantity}"
           price_str = f"{int(t_price):>10}"
          
           # Calculate padding between text and price
           # 32 total chars - price_str (10) = 22 chars for the left side
           raw_data += f"{item_line_left:<22}{price_str}\n".encode('cp866')


       raw_data += (("-" * 32) + "\n").encode('cp866')
      
       # TOTAL (Right Align + Bold)
       raw_data += b'\x1b\x61\x02'
       raw_data += b'\x1b\x45\x01' # Bold ON
       raw_data += f"ИТОГО: {grand_total} СОМ\n".encode('cp866')
       raw_data += b'\x1b\x45\x00' # Bold OFF
      
       # FOOTER (Center Align)
       raw_data += b'\x1b\x61\x01'
       raw_data += "\nСпасибо, что выбрали нас!\n".encode('cp866')
      
       # CONDITIONAL: Only print full date/time at the very bottom if closed
       if finish_time:
           raw_data += f"{current_time_local.strftime('%d.%m.%Y %H:%M')}\n".encode('cp866')
      
       # Feed and Cut
       raw_data += b"\n\n\n\n\n"
       raw_data += b"\x1d\x56\x01"


       # --- 3. Send to Windows Spooler ---
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
       traceback.print_exc()
