# catalog/urls.py
from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.MediaItemListView.as_view(), name='mediaitem_list'),
    path('item/<int:pk>/', views.MediaItemDetailView.as_view(), name='mediaitem_detail'),
    path('play/<int:pk>/', views.PlaySourceLinkView.as_view(), name='play_source_link'),
    path('search/', views.MediaItemSearchView.as_view(), name='mediaitem_search'),
]
