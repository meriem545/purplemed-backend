from django.contrib import admin
from .models import Patient, DoctorProfile, Appointment, Schedule

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'phone_number', 'is_active']
    search_fields = ['user__email', 'phone_number']

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'specialization', 'is_available']
    search_fields = ['user__email', 'license_number']

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'doctor', 'appointment_date', 'status']
    list_filter = ['status', 'appointment_date']

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'day_of_week', 'start_time', 'end_time']