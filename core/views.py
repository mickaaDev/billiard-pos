from django.shortcuts import render, get_object_or_404, redirect
from .models import Resource, Product, Session, SessionItem, Bill, Shift
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone 
from django.contrib import messages
from decimal import Decimal
from django.http import JsonResponse
from .utils import print_receipt_58mm
# Create your views here.



def print_session_bill(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    items = session.items.all()
    
    # Считаем товары
    items_total = sum(item.total_price() if callable(item.total_price) else item.total_price for item in items)
    
    # Определяем время окончания (текущее или из базы)
    finish_time = session.end_time if session.end_time else timezone.now()
    
    duration_min = 0
    if session.start_time:
        duration = finish_time - session.start_time
        duration_min = int(max(0, duration.total_seconds() / 60))
        price_per_minute = session.resource.price_per_hour / 60
        time_cost = Decimal(duration_min) * price_per_minute
    else:
        time_cost = Decimal('0')

    grand_total = int(items_total + time_cost)
    
    # Передаем всё в функцию печати (добавили duration_min и finish_time)
    print_receipt_58mm(session, items, grand_total, finish_time, duration_min)
    
    # ЛОГИКА РЕДИРЕКТА:
    if not session.is_active or session.end_time:
        # Если сессия закрыта, идем на главную (dashboard)
        return redirect('core:dashboard') 
    else:
        # Если сессия еще идет, остаемся в деталях
        return redirect('core:session_detail', pk=session.id)


@login_required
def dashboard(request):
    active_shift = Shift.objects.filter(is_active=True).first()
    resources = Resource.objects.all()
    now = timezone.now()
    resources_with_sessions = []
    if not active_shift:
        return redirect('core:start_shift')
    for r in resources:
        session = r.current_session()
        is_overtime = False
        if session and session.mode == 'PREPAID' and session.prepaid_minutes:
            limit_time = session.start_time + timezone.timedelta(minutes=session.prepaid_minutes)
            is_overtime = now > limit_time
        
        resources_with_sessions.append({
            'resource': r,
            'session': session,
            'is_overtime': is_overtime
        })

    return render(request, 'core/dashboard.html', {'resources_with_sessions': resources_with_sessions})

@login_required
def resource_details(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    # Check for the current active session
    active_session = Session.objects.filter(resource=resource, is_active=True).first()
    
    return render(request, 'core/resource_details.html', {
        'resource': resource,
        'active_session': active_session # Changed to single object for easier template logic
    })


@login_required
@require_POST
def start_session(request, resource_id):
    if request.method == 'POST':
        resource = get_object_or_404(Resource, id=resource_id)
        active_shift = Shift.objects.filter(is_active=True).first()
        if not active_shift:
            messages.error(request, "Нельзя открыть стол без открытой смены!")
            return redirect('core:start_shift')
        # Check if table is already busy
        if Session.objects.filter(resource=resource, is_active=True).exists():
            messages.error(request, "This resource already has an active session.")
            return redirect('core:dashboard')

        mode = request.POST.get('mode', 'OPEN')
        duration_min = request.POST.get('duration')
        
        prepaid_mins = None
        if mode == 'PREPAID':
            # Validation: Ensure duration is provided and is a positive number
            try:
                if duration_min and int(duration_min) > 0:
                    prepaid_mins = int(duration_min)
                else:
                    messages.error(request, "Please enter a valid amount or duration for Prepaid mode.")
                    return redirect('core:resource_details', pk=resource_id)
            except ValueError:
                messages.error(request, "Invalid duration format.")
                return redirect('core:resource_details', pk=resource_id)

        # Create the session
        new_session = Session.objects.create(
            resource=resource,
            created_by=request.user,
            shift=active_shift,
            mode=mode,
            prepaid_minutes=prepaid_mins,
            is_active=True,
            start_time=timezone.now()
        )

        messages.success(request, f"Session started for {resource.name}")
        return redirect('core:session_detail', pk=new_session.pk)
    
    return redirect('core:dashboard')


def extend_session(request, pk):
    if request.method == "POST":
        session = get_object_or_404(Session, pk=pk, is_active=True)
        extra_minutes = request.POST.get('extra_minutes')

        try:
            extra_minutes = int(extra_minutes)
            if extra_minutes > 0:
                session.prepaid_minutes += extra_minutes
                session.save()
                messages.success(request, f"Сессия продлена на {extra_minutes} мин.")
            else:
                messages.error(request, "Введите корректное количество минут.")
        except (ValueError, TypeError):
            messages.error(request, "Ошибка при продлении сессии.")
            
        return redirect('core:session_detail', pk=session.pk)
    return redirect('core:dashboard')


@login_required
def remove_item_from_session(request, item_id):
    if request.method == "POST":
        item = get_object_or_404(SessionItem, id=item_id)
        session_id = item.session.id

        if item.session.is_active:
            product = item.product
            
            # 1. Logic for Decremental Removal
            if item.quantity > 1:
                item.quantity -= 1
                item.save()
                message_text = f"Удалена 1 шт. {product.name}. Осталось в заказе: {item.quantity}"
            else:
                # If it's the last one, remove the row entirely
                item.delete()
                message_text = f"Товар {product.name} полностью удален из заказа"

            # 2. Always return exactly 1 to the stock
            product.stock += 1
            product.save()

            messages.success(request, message_text)
        else:
            messages.error(request, "Нельзя изменять закрытую сессию.")
        
        return redirect('core:session_detail', pk=session_id)
    
    return redirect('core:dashboard')

@login_required
def session_detail(request, pk):
    session = get_object_or_404(Session, pk=pk)
    now = timezone.now()
    
    # 1. Calculate Exact Time
    diff = now - session.start_time
    total_seconds = diff.total_seconds()
    # Use float/decimal for minutes to avoid the "0" problem
    duration_minutes_float = total_seconds / 60
    # For display as an integer
    duration_minutes_display = int(duration_minutes_float)
    
    price_per_hour = Decimal(str(session.resource.price_per_hour))
    price_per_minute = price_per_hour / Decimal(60)

    # 2. Determine Billable Time & Cost
    if session.mode == 'PREPAID' and session.prepaid_minutes:
        # Prepaid stays fixed at the bought amount
        billable_minutes = Decimal(session.prepaid_minutes)
        
        limit_time = session.start_time + timezone.timedelta(minutes=session.prepaid_minutes)
        remaining_seconds = max(0, (limit_time - now).total_seconds())
        is_expired = now >= limit_time
        overtime_minutes = max(0, duration_minutes_display - session.prepaid_minutes)
    else:
        # OPEN SESSION: Calculate real-time cost
        # We use the float here so even 30 seconds shows a small cost
        billable_minutes = Decimal(duration_minutes_float)
        remaining_seconds = 0
        is_expired = False
        overtime_minutes = 0

    # 3. Final Calculations
    time_cost = billable_minutes * price_per_minute
    session_items = session.items.all().order_by('id') # Force stable order
    product_total = sum(item.total_price() for item in session_items)
    grand_total = time_cost + Decimal(product_total)

    products = Product.objects.all().order_by('name')

    return render(request, "core/session_detail.html", {
        "session": session,
        "session_items": session_items,
        "duration_minutes": duration_minutes_display,
        "time_cost": round(time_cost, 2),
        "product_total": round(product_total, 2),
        "grand_total": round(grand_total, 2),
        "products": products,
        "remaining_seconds": int(remaining_seconds),
        "is_expired": is_expired,
        "overtime_minutes": overtime_minutes
    })

@login_required
def bill_summary(request, pk):
    session = get_object_or_404(Session, pk=pk)
    bill = get_object_or_404(Bill, session=session)
    
    duration = session.end_time - session.start_time
    duration_minutes = int(duration.total_seconds() / 60)
    
    product_total = sum(item.total_price() for item in session.items.all())
    
    time_cost = bill.total_amount - Decimal(product_total)

    return render(request, "core/bill_summary.html", {
        "session": session,
        "duration_minutes": duration_minutes, 
        "time_cost": round(time_cost, 2),
        "product_total": round(product_total, 2),
        "grand_total": bill.total_amount,
    })

@require_POST
@login_required
def close_session(request, pk):
    session = get_object_or_404(Session, pk=pk)
    session.end_time = timezone.now()
    session.is_active = False
    session.save()

    duration = session.end_time - session.start_time
    actual_minutes = int(duration.total_seconds() / 60)
    
    if session.mode == 'PREPAID':
        charge_overtime = request.POST.get('charge_overtime') == 'true'
        
        if charge_overtime:
            billable_minutes = actual_minutes
        else:
            billable_minutes = session.prepaid_minutes
    else:
        billable_minutes = actual_minutes

    price_per_minute = Decimal(str(session.resource.price_per_hour)) / Decimal(60)
    time_cost = Decimal(billable_minutes) * price_per_minute
    
    product_total = sum(item.total_price() for item in session.items.all())
    final_total = time_cost + Decimal(product_total)

    # 4. Save the Bill record
    Bill.objects.create(
        session=session,
        total_amount=round(final_total, 2)
    )

    return redirect('core:bill_summary', pk=session.pk)

@require_POST
@login_required
def add_item_to_session(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    product = get_object_or_404(Product, id=request.POST.get('product_id'))

    if product.stock < 1:
        messages.error(request, f"Товар '{product.name}' закончился!")
        return redirect('core:session_detail', pk=session.pk)

    item, created = SessionItem.objects.get_or_create(
        session=session,
        product=product,
        defaults={
            'price_at_order': product.price,
            'quantity': 0
        }
    )
    
    if item.price_at_order is None:
        item.price_at_order = product.price
        
    item.quantity += 1
    item.save()

    product.stock -= 1
    product.save()

    messages.success(request, f"Добавлено: {product.name}")
    return redirect('core:session_detail', pk=session.pk)


@login_required
def dashboard_api(request):
    resources = Resource.objects.all()
    now = timezone.now()
    data = []

    for r in resources:
        session = r.current_session()
        is_overtime = False
        if session and session.mode == 'PREPAID' and session.prepaid_minutes:
            limit_time = session.start_time + timezone.timedelta(minutes=session.prepaid_minutes)
            is_overtime = now > limit_time
        
        data.append({
            'id': r.id,
            'is_active': session is not None,
            'is_overtime': is_overtime,
        })

    return JsonResponse({'resources': data})


@login_required
def start_shift(request):
    if request.method == "POST":
        amount = request.POST.get('start_cash', 0)
        Shift.objects.create(
            user=request.user,
            start_cash=amount,
            is_active=True
        )
        messages.success(request, "Смена открыта!")
        return redirect('core:dashboard')
    return render(request, 'core/start_shift.html')

@login_required
def close_shift(request):
    active_shift = Shift.objects.filter(is_active=True).first()
    
    if not active_shift:
        messages.warning(request, "У вас нет активной смены.")
        return redirect('core:dashboard')

    # BLOCKER: Check if any session is still running
    if Session.objects.filter(is_active=True).exists():
        messages.error(request, "Нельзя закрыть смену! Есть открытые столы. Сначала завершите все активные сессии.")
        return redirect('core:dashboard')

    report = active_shift.get_shift_report()
    expected_cash = active_shift.start_cash + report['total_revenue']

    if request.method == "POST":
        active_shift.end_time = timezone.now()
        # Save what the staff actually counted
        active_shift.end_cash = request.POST.get('end_cash')
        active_shift.is_active = False
        active_shift.save()
        
        messages.success(request, f"Смена успешно закрыта. Ожидалось: {expected_cash}, Введено: {active_shift.end_cash}")
        return redirect('/')

    return render(request, 'core/close_shift.html', {
        'shift': active_shift,
        'report': report,
        'expected_cash': expected_cash
    })