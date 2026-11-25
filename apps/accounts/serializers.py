from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=254, help_text="Username or email address.")
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, user) -> str:
        return user.get_full_name() or user.get_username()
