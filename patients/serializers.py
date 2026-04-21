from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Patient, DoctorProfile, Appointment, Schedule
from .services import AppointmentService

User = get_user_model()


class PatientSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    age = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Patient
        fields = [
            'id', 'user', 'user_email', 'user_name', 'date_of_birth', 'age',
            'gender', 'blood_type', 'phone_number', 'address',
            'emergency_contact_name', 'emergency_contact_phone', 'allergies',
            'chronic_conditions', 'insurance_provider', 'insurance_number',
            'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_user_name(self, obj):
        return obj.user.get_full_name()


class DoctorProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    specialization_display = serializers.CharField(source='get_specialization_display', read_only=True)
    
    class Meta:
        model = DoctorProfile
        fields = [
            'id', 'user', 'user_name', 'specialization', 'specialization_display',
            'license_number', 'years_of_experience', 'consultation_fee',
            'available_days', 'consultation_duration', 'max_patients_per_day',
            'is_available', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_user_name(self, obj):
        return obj.user.get_full_name()


class ScheduleSerializer(serializers.ModelSerializer):
    day_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Schedule
        fields = ['id', 'doctor', 'day_of_week', 'day_display', 'start_time', 'end_time', 'is_break']
    
    def get_day_display(self, obj):
        return obj.get_day_of_week_display()


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
    doctor_specialization = serializers.CharField(source='doctor.get_specialization_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'doctor', 'doctor_name',
            'doctor_specialization', 'appointment_date', 'start_time',
            'end_time', 'status', 'status_display', 'reason', 'notes',
            'is_emergency', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AppointmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['patient', 'doctor', 'appointment_date', 'start_time', 'end_time', 'reason', 'is_emergency']
    
    def validate(self, data):
        is_available, message = AppointmentService.check_availability(
            data['doctor'].id,
            data['appointment_date'],
            data['start_time'],
            data['end_time']
        )
        
        if not is_available:
            raise serializers.ValidationError(message)
        
        return data
    
    def create(self, validated_data):
        validated_data['status'] = 'SCHEDULED'
        return super().create(validated_data)


class AppointmentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['status', 'notes']