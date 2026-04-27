from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdmin(BasePermission):
    message = 'Access restricted to administrators only.'
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'admin')

class IsDoctor(BasePermission):
    message = 'Access restricted to doctors only.'
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'doctor')

class IsPatient(BasePermission):
    message = 'Access restricted to patients only.'
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'patient')

class IsAdminOrDoctor(BasePermission):
    message = 'Access restricted to admins and doctors.'
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ('admin', 'doctor'))

class IsOwnerOrAdmin(BasePermission):
    message = 'You can only access your own data.'
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        return obj == request.user

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role == 'admin'