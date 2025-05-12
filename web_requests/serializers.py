import jdatetime
from rest_framework import serializers


class JalaliDateTimeField(serializers.Field):
    """
    Custom field for Jalali DateTime conversion with time preservation
    - Accepts multiple Jalali datetime formats
    - Converts to Gregorian datetime while preserving time
    - Handles default time values for missing time components
    """
    
    DEFAULT_FORMATS = [
        '%Y-%m-%d %H:%M:%S',  # Full format with seconds
        '%Y-%m-%d %H:%M',     # Without seconds
        '%Y-%m-%d'             # Date only
    ]
    
    def __init__(self, formats=None, default_time=None, *args, **kwargs):
        """
        :param formats: List of accepted Jalali formats
        :param default_time: Tuple (hour, minute, second) for missing time
        """
        self.formats = formats or self.DEFAULT_FORMATS
        self.default_time = default_time or (0, 0, 0)
        super().__init__(*args, **kwargs)

    def to_representation(self, value):
        """Convert Gregorian datetime to Jalali string with original format"""
        if value is None:
            return None
            
        # Preserve original time components
        jalali_dt = jdatetime.datetime.fromgregorian(datetime=value)
        return jalali_dt.strftime(self.formats[0])

    def to_internal_value(self, data):
        """Convert Jalali string to Gregorian datetime with time handling"""
        for fmt in self.formats:
            try:
                parsed = jdatetime.datetime.strptime(data, fmt)
                break
            except ValueError:
                continue
        else:
            raise serializers.ValidationError(
                f"Invalid format. Allowed formats: {', '.join(self.formats)}"
            )

        # Apply default time if needed
        if parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
            parsed = parsed.replace(
                hour=self.default_time[0],
                minute=self.default_time[1],
                second=self.default_time[2]
            )

        return parsed.togregorian()

class DynamicRequestSerializer(serializers.Serializer):

    type_mapping = {
        "string": serializers.CharField,
        "integer": serializers.IntegerField,
        "boolean": serializers.BooleanField,
        "date": serializers.DateField,
        "jdate": lambda **kwargs: JalaliDateTimeField(formats=['%Y/%m/%d %H:%M:%S'], **kwargs),
        "list_string": lambda: serializers.ListField(child=serializers.CharField()),
        "list_integer": lambda: serializers.ListField(child=serializers.IntegerField())
    }
        
    def __init__(self, *args, **kwargs):
        request_foreign = kwargs.pop('request_foreign', None)
        super().__init__(*args, **kwargs)
        
        if request_foreign:
            
            for param, type in request_foreign.get_query_parameters().items():
                self.fields[param] = self.type_mapping[type](required=False)

            for param, type in request_foreign.get_body_parameters().items():
                self.fields[param] = self.type_mapping[type](required=False)

class SendCodeSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    type = serializers.CharField()
