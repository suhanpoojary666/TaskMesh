from django.shortcuts import render
from .models import *
from .serializers import *
from rest_framework.response import Response
from rest_framework.decorators import api_view


# Create your views here.

@api_view(["POST"])
def create_task(request):

    serializer=TaskCreateSerializer(data=request.data)

    if not serializer.is_valid():

        return Response({
            "messege":"Invalid data"
        },status=400)

    data=serializer.validated_data

    task=Task(callback_url=data["callback_url"],
        method=data["method"],
        payload=data["payload"])

    task.save();

    return Response({
        "id":task.id,
        "status":task.status
    },status=200)




