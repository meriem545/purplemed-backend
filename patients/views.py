from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Patient, DoctorProfile, Appointment, Schedule
from .serializers import (
    PatientSerializer, DoctorProfileSerializer, AppointmentSerializer,
    AppointmentCreateSerializer, AppointmentUpdateSerializer, ScheduleSerializer
)
from .services import AppointmentService, PatientService, DoctorAvailabilityService


class IsPatientOwner(permissions.BasePermission):
    """Custom permission to allow patients to only access their own data"""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if hasattr(obj, 'patient'):
            return obj.patient.user == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class PatientViewSet(viewsets.ModelViewSet):
    """ViewSet for managing patients"""
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    
    def get_permissions(self):
        if self.action in ['create']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Patient.objects.all()
        return Patient.objects.filter(user=user)
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get complete patient history"""
        patient = self.get_object()
        include_appointments = request.query_params.get('appointments', 'true') == 'true'
        include_medical = request.query_params.get('medical', 'true') == 'true'
        
        history = PatientService.get_patient_history(
            patient.id,
            include_appointments,
            include_medical
        )
        return Response(history)
    
    @action(detail=True, methods=['get'])
    def appointments(self, request, pk=None):
        """Get patient's appointments"""
        patient = self.get_object()
        upcoming = request.query_params.get('upcoming', 'false') == 'true'
        
        if upcoming:
            appointments = PatientService.get_upcoming_appointments(patient.id)
        else:
            appointments = Appointment.objects.filter(patient=patient)
        
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get patient statistics"""
        patient = self.get_object()
        stats = PatientService.get_patient_statistics(patient.id)
        return Response(stats)


class DoctorProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for managing doctor profiles"""
    queryset = DoctorProfile.objects.all()
    serializer_class = DoctorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return DoctorProfile.objects.all()
        
        try:
            return DoctorProfile.objects.filter(user=user)
        except DoctorProfile.DoesNotExist:
            return DoctorProfile.objects.none()
    
    @action(detail=True, methods=['get'])
    def available_slots(self, request, pk=None):
        """Get available time slots for a doctor on a specific date"""
        doctor = self.get_object()
        date = request.query_params.get('date')
        
        if not date:
            return Response({'error': 'Date parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from datetime import datetime
            appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
        
        slots = AppointmentService.get_available_slots(doctor.id, appointment_date)
        return Response(slots)
    
    @action(detail=True, methods=['get'])
    def today_schedule(self, request, pk=None):
        """Get doctor's schedule for today"""
        doctor = self.get_object()
        schedule = DoctorAvailabilityService.get_doctor_today_schedule(doctor.id)
        
        appointments_serializer = AppointmentSerializer(schedule['appointments'], many=True)
        schedule_serializer = ScheduleSerializer(schedule['schedules'], many=True)
        
        return Response({
            'schedules': schedule_serializer.data,
            'appointments': appointments_serializer.data,
            'available_slots': schedule['available_slots']
        })
    
    @action(detail=True, methods=['post'])
    def set_schedule(self, request, pk=None):
        """Set doctor's weekly schedule"""
        doctor = self.get_object()
        schedule_data = request.data.get('schedule', [])
        
        try:
            schedules = DoctorAvailabilityService.update_doctor_schedule(doctor.id, schedule_data)
            serializer = ScheduleSerializer(schedules, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AppointmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing appointments"""
    queryset = Appointment.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsPatientOwner]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AppointmentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return AppointmentUpdateSerializer
        return AppointmentSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Appointment.objects.all()
        
        if user.is_staff:
            return queryset
        
        try:
            patient = Patient.objects.get(user=user)
            return queryset.filter(patient=patient)
        except Patient.DoesNotExist:
            pass
        
        try:
            doctor = DoctorProfile.objects.get(user=user)
            return queryset.filter(doctor=doctor)
        except DoctorProfile.DoesNotExist:
            pass
        
        return queryset.none()
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an appointment"""
        appointment = self.get_object()
        
        if appointment.appointment_date < timezone.now().date():
            return Response({'error': 'Cannot cancel past appointments'}, status=status.HTTP_400_BAD_REQUEST)
        
        appointment.status = 'CANCELLED'
        appointment.save()
        
        return Response({'message': 'Appointment cancelled successfully'})
    
    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        """Reschedule an appointment"""
        appointment = self.get_object()
        
        new_date = request.data.get('appointment_date')
        new_start_time = request.data.get('start_time')
        new_end_time = request.data.get('end_time')
        
        if not all([new_date, new_start_time, new_end_time]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from datetime import datetime
            new_date_obj = datetime.strptime(new_date, '%Y-%m-%d').date()
            new_start_obj = datetime.strptime(new_start_time, '%H:%M').time()
            new_end_obj = datetime.strptime(new_end_time, '%H:%M').time()
            
            updated_appointment = AppointmentService.reschedule_appointment(
                appointment.id,
                new_date_obj,
                new_start_obj,
                new_end_obj,
                request.user
            )
            
            serializer = AppointmentSerializer(updated_appointment)
            return Response(serializer.data)
            
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming appointments for the logged-in user"""
        user = request.user
        today = timezone.now().date()
        
        try:
            patient = Patient.objects.get(user=user)
            appointments = Appointment.objects.filter(
                patient=patient,
                appointment_date__gte=today,
                status__in=['SCHEDULED', 'CONFIRMED']
            ).order_by('appointment_date', 'start_time')
        except Patient.DoesNotExist:
            try:
                doctor = DoctorProfile.objects.get(user=user)
                appointments = Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date__gte=today,
                    status__in=['SCHEDULED', 'CONFIRMED']
                ).order_by('appointment_date', 'start_time')
            except DoctorProfile.DoesNotExist:
                appointments = Appointment.objects.none()
        
        serializer = AppointmentSerializer(appointments, many=True)
        return Response(serializer.data)

