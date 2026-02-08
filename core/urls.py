from django.urls import path
from . import views


app_name = "core"

urlpatterns = [
    # ... your existing paths ...
    path('', views.dashboard, name='dashboard'),
    path('resource/<int:pk>/', views.resource_details, name='resource_details'),
    path('session/start/<int:resource_id>/', views.start_session, name='start_session'),
    path('session/<int:pk>/', views.session_detail, name='session_detail'),
    path('session/close/<int:pk>/', views.close_session, name='close_session'),
    path('session/<int:pk>/bill/', views.bill_summary, name='bill_summary'),
    path('session/<int:session_pk>/add-item/', views.add_item_to_session, name='add_item_to_session'),
    path('item/remove/<int:item_id>/', views.remove_item_from_session, name='remove_item_from_session'),
    path('session/extend/<int:pk>/', views.extend_session, name='extend_session'),
    path('dashboard/api/', views.dashboard_api, name='dashboard_api'),
    path('shift/start/', views.start_shift, name='start_shift'),
    path('shift/close/', views.close_shift, name='close_shift'),
]