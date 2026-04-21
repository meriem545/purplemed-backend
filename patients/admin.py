from django.contrib import admin
from .models import Patient, DoctorProfile, Appointment, Schedule

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'phone_number', 'blood_type', 'is_active']
    list_filter = ['gender', 'blood_type', 'is_active']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'specialization', 'license_number', 'is_available']
    list_filter = ['specialization', 'is_available']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'license_number']

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'doctor', 'appointment_date', 'start_time', 'status']
    list_filter = ['status', 'appointment_date', 'is_emergency']
    search_fields = ['patient__user__email', 'doctor__user__email']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'day_of_week', 'start_time', 'end_time', 'is_break']
    list_filter = ['day_of_week', 'is_break']
    search_fields = ['doctor__user__email']