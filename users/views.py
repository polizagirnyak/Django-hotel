from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages


def admin_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None and user.is_staff:
                login(request, user)
                return redirect('index')
            else:
                messages.error(request, 'Неверные учетные данные или недостаточно прав')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
    else:
        form = AuthenticationForm()

    return render(request, template_name='users/admin_login.html', context={'form':form})
