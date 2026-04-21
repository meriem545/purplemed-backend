from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Appointment, DoctorProfile, Patient, Schedule


class AppointmentService:
    """Handles appointment business logic"""
    
    @staticmethod
    def check_availability(doctor_id, appointment_date, start_time, end_time, exclude_appointment_id=None):
        """Check if doctor is available at given time"""
        from .models import DoctorProfile, Appointment, Schedule
        
        try:
            doctor = DoctorProfile.objects.get(id=doctor_id)
        except DoctorProfile.DoesNotExist:
            return False, "Doctor not found"
        
        day_of_week = appointment_date.weekday()
        
        schedule_exists = Schedule.objects.filter(
            doctor=doctor,
            day_of_week=day_of_week,
            is_break=False,
            start_time__lte=start_time,
            end_time__gte=end_time
        ).exists()
        
        if not schedule_exists:
            return False, "Doctor not available at this time"
        
        conflicting_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date,
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        )
        
        if exclude_appointment_id:
            conflicting_appointments = conflicting_appointments.exclude(id=exclude_appointment_id)
        
        for appointment in conflicting_appointments:
            if (start_time < appointment.end_time and end_time > appointment.start_time):
                return False, f"Conflict with existing appointment at {appointment.start_time}"
        
        today_appointments = conflicting_appointments.filter(
            appointment_date=appointment_date
        ).count()
        
        if today_appointments >= doctor.max_patients_per_day:
            return False, f"Doctor has reached maximum {doctor.max_patients_per_day} patients for today"
        
        return True, "Slot available"
    
    @staticmethod
    def get_available_slots(doctor_id, date):
        from .models import DoctorProfile, Appointment, Schedule
        
        try:
            doctor = DoctorProfile.objects.get(id=doctor_id)
        except DoctorProfile.DoesNotExist:
            return []
        
        day_of_week = date.weekday()
        
        schedules = Schedule.objects.filter(
            doctor=doctor,
            day_of_week=day_of_week,
            is_break=False
        )
        
        if not schedules.exists():
            return []
        
        booked_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=date,
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        ).values_list('start_time', 'end_time')
        
        available_slots = []
        duration_minutes = doctor.consultation_duration
        
        for schedule in schedules:
            current_time = datetime.combine(date, schedule.start_time)
            end_time = datetime.combine(date, schedule.end_time)
            
            while current_time + timedelta(minutes=duration_minutes) <= end_time:
                slot_start = current_time.time()
                slot_end = (current_time + timedelta(minutes=duration_minutes)).time()
                
                is_booked = any(
                    booked_start <= slot_start < booked_end or
                    booked_start < slot_end <= booked_end or
                    (slot_start <= booked_start and slot_end >= booked_end)
                    for booked_start, booked_end in booked_appointments
                )
                
                if not is_booked:
                    available_slots.append({
                        'start_time': slot_start.strftime('%H:%M'),
                        'end_time': slot_end.strftime('%H:%M')
                    })
                
                current_time += timedelta(minutes=duration_minutes)
        
        return available_slots
    
    @staticmethod
    def reschedule_appointment(appointment_id, new_date, new_start_time, new_end_time, user):
        appointment = Appointment.objects.get(id=appointment_id, patient__user=user)
        
        is_available, message = AppointmentService.check_availability(
            appointment.doctor.id,
            new_date,
            new_start_time,
            new_end_time,
            exclude_appointment_id=appointment_id
        )
        
        if not is_available:
            raise ValidationError(message)
        
        appointment.appointment_date = new_date
        appointment.start_time = new_start_time
        appointment.end_time = new_end_time
        appointment.status = 'SCHEDULED'
        appointment.save()
        
        return appointment


class PatientService:
    """Handles patient-related business logic"""
    
    @staticmethod
    def get_patient_history(patient_id, include_appointments=True, include_medical=True):
        patient = Patient.objects.get(id=patient_id)
        
        history = {
            'patient_info': {
                'name': patient.user.get_full_name(),
                'age': patient.age,
                'blood_type': patient.blood_type,
                'allergies': patient.allergies,
                'chronic_conditions': patient.chronic_conditions
            }
        }
        
        if include_appointments:
            appointments = Appointment.objects.filter(
                patient=patient
            ).select_related('doctor').order_by('-appointment_date')
            
            history['appointments'] = [
                {
                    'id': apt.id,
                    'date': apt.appointment_date,
                    'doctor': apt.doctor.user.get_full_name(),
                    'specialization': apt.doctor.get_specialization_display(),
                    'reason': apt.reason,
                    'status': apt.status,
                    'notes': apt.notes
                }
                for apt in appointments
            ]
        
        if include_medical:
            history['medical_records'] = []
        
        return history
    
    @staticmethod
    def get_upcoming_appointments(patient_id):
        today = timezone.now().date()
        
        return Appointment.objects.filter(
            patient_id=patient_id,
            appointment_date__gte=today,
            status__in=['SCHEDULED', 'CONFIRMED']
        ).select_related('doctor').order_by('appointment_date', 'start_time')
    
    @staticmethod
    def get_patient_statistics(patient_id):
        appointments = Appointment.objects.filter(patient_id=patient_id)
        
        return {
            'total_appointments': appointments.count(),
            'completed_appointments': appointments.filter(status='COMPLETED').count(),
            'cancelled_appointments': appointments.filter(status='CANCELLED').count(),
            'no_shows': appointments.filter(status='NO_SHOW').count(),
            'last_visit': appointments.filter(status='COMPLETED').order_by('-appointment_date').first()
        }


class DoctorAvailabilityService:
    """Handles doctor availability logic"""
    
    @staticmethod
    def get_doctor_today_schedule(doctor_id):
        today = timezone.now().date()
        day_of_week = today.weekday()
        
        schedules = Schedule.objects.filter(
            doctor_id=doctor_id,
            day_of_week=day_of_week
        )
        
        today_appointments = Appointment.objects.filter(
            doctor_id=doctor_id,
            appointment_date=today,
            status__in=['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS']
        )
        
        return {
            'schedules': schedules,
            'appointments': today_appointments,
            'available_slots': AppointmentService.get_available_slots(doctor_id, today)
        }
    
    @staticmethod
    def update_doctor_schedule(doctor_id, schedule_data):
        doctor = DoctorProfile.objects.get(id=doctor_id)
        
        Schedule.objects.filter(doctor=doctor).delete()
        
        for day_schedule in schedule_data:
            Schedule.objects.create(
                doctor=doctor,
                day_of_week=day_schedule['day'],
                start_time=day_schedule['start_time'],
                end_time=day_schedule['end_time'],
                is_break=day_schedule.get('is_break', False)
            )
        
        return doctor.schedules.all()