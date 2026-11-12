from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/<slug:slug>/', views.project_detail, name='project_detail'),
    path('projects/<slug:slug>/plots/<slug:plot_slug>/', views.plot_detail, name='plot_detail'),
    path('locations/', views.locations, name='locations'),
    path('locations/<slug:slug>/', views.area_detail, name='area_detail'),
    path('gallery/', views.gallery, name='gallery'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('testimonials/', views.testimonials, name='testimonials'),
    path('insights/', views.articles, name='articles'),
    path('insights/<slug:slug>/', views.article, name='article'),
    path('pages/<slug:slug>/', views.page, name='page'),
    path('api/projects/', views.project_api, name='project_api'),
    path('api/projects/<slug:slug>/plots/', views.plot_api, name='plot_api'),
    path('api/layouts/<int:pk>/plots/', views.editor_api, name='editor_api'),
    path('api/enquiries/', views.enquiry_api, name='enquiry_api'),
    path('admin/estate/projectlayout/<int:pk>/editor/', views.layout_editor, name='layout_editor'),
    path('sitemap.xml', views.sitemap, name='sitemap'),
    path('robots.txt', views.robots, name='robots'),
]
