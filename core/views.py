from django.shortcuts import render, get_object_or_404, redirect
from .models import Resource, Product, Session, SessionItem, Bill
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone 
from django.contrib import messages
from decimal import Decimal
from django.http import JsonResponse
# Create your views here.

@login_required
def dashboard(request):
    resources = Resource.objects.all()
    now = timezone.now()
    resources_with_sessions = []

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
        
        # Check if table is already busy to prevent double-booking
        if Session.objects.filter(resource=resource, is_active=True).exists():
            messages.error(request, "This resource already has an active session.")
            return redirect('core:dashboard')

        mode = request.POST.get('mode', 'OPEN')
        duration_min = request.POST.get('duration')
        
        prepaid_mins = None
        if mode == 'PREPAID' and duration_min:
            prepaid_mins = int(duration_min)

        # Create the session
        new_session = Session.objects.create(
            resource=resource,
            created_by=request.user,
            mode=mode,
            prepaid_minutes=prepaid_mins,
            is_active=True,
            start_time=timezone.now()
        )

        messages.success(request, f"Session started for {resource.name}")
        # REDIRECT to the session detail page
        return redirect('core:session_detail', pk=new_session.pk)
    
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
    product_total = sum(item.total_price() for item in session.items.all())
    grand_total = time_cost + Decimal(product_total)

    products = Product.objects.all()

    return render(request, "core/session_detail.html", {
        "session": session,
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
    # Get the bill record created during close_session
    bill = get_object_or_404(Bill, session=session)
    
    # Calculate final duration for display purposes
    duration = session.end_time - session.start_time
    duration_minutes = int(duration.total_seconds() / 60)
    
    # Calculate product total
    product_total = sum(item.total_price() for item in session.items.all())
    
    # The time cost is whatever is left in the bill after subtracting products
    time_cost = bill.total_amount - Decimal(product_total)

    return render(request, "core/bill_summary.html", {
        "session": session,
        "duration_minutes": duration_minutes, 
        "time_cost": round(time_cost, 2),
        "product_total": round(product_total, 2),
        "grand_total": bill.total_amount, # Use the actual saved amount
    })

@require_POST
@login_required
def close_session(request, pk):
    session = get_object_or_404(Session, pk=pk)
    session.end_time = timezone.now()
    session.is_active = False
    session.save()

    # 1. Calculate Real Elapsed Time
    duration = session.end_time - session.start_time
    actual_minutes = int(duration.total_seconds() / 60)
    
    # 2. Determine Billable Minutes
    if session.mode == 'PREPAID':
        # Check if the "Charge Overtime" checkbox was ticked in the form
        charge_overtime = request.POST.get('charge_overtime') == 'true'
        
        if charge_overtime:
            # Charge for every minute they actually stayed
            billable_minutes = actual_minutes
        else:
            # Stick to the original prepaid limit
            billable_minutes = session.prepaid_minutes
    else:
        # For OPEN sessions, always charge actual time
        billable_minutes = actual_minutes

    # 3. Calculate Final Money
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

    item, created = SessionItem.objects.get_or_create(
        session=session,
        product=product,
        defaults={
            'price_at_order': product.price, # CRITICAL: captures the price
            'quantity': 0
        }
    )
    
    # If the item existed but had no price (from old bugs), fix it now
    if item.price_at_order is None:
        item.price_at_order = product.price
        
    item.quantity += 1
    item.save()

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