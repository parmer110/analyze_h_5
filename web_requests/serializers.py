from rest_framework import serializers

class SendCodeSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    type = serializers.CharField()

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    code = serializers.CharField()

class cm10Serializer(serializers.Serializer):
    export_data = serializers.CharField()
    call_type = serializers.ListField(child=serializers.CharField())
    start_at = serializers.CharField()
    end_at = serializers.CharField()