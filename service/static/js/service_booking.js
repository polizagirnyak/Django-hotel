// static/js/service_booking.js
class ServiceBookingForm {
    constructor() {
        this.serviceSelect = document.getElementById('id_service');
        this.bookingDateInput = document.getElementById('id_booking_date');
        this.startTimeInput = document.getElementById('id_start_time');
        this.participantsInput = document.getElementById('id_participants');
        this.serviceInfo = document.getElementById('service-info');
        this.bookingTimeInfo = document.getElementById('booking-time-info');

        this.serviceData = {};
        this.initialize();
    }

    initialize() {
        // Собираем данные об услугах из data-атрибутов
        this.loadServiceData();

        // Назначаем обработчики событий
        this.bindEvents();

        // Инициализируем форму
        this.updateForm();
    }

    loadServiceData() {
        // Данные должны быть переданы из шаблона
        // Например: <div id="service-data" data-services='{{ services_json|safe }}'></div>
        const serviceDataElement = document.getElementById('service-data');
        if (serviceDataElement) {
            this.serviceData = JSON.parse(serviceDataElement.dataset.services);
        }
    }

    bindEvents() {
        if (this.serviceSelect) {
            this.serviceSelect.addEventListener('change', () => this.onServiceChange());
        }

        if (this.bookingDateInput) {
            this.bookingDateInput.addEventListener('change', () => this.onDateChange());
        }

        if (this.startTimeInput) {
            this.startTimeInput.addEventListener('change', () => this.onTimeChange());
        }

        if (this.participantsInput) {
            this.participantsInput.addEventListener('input', () => this.updateTotalPrice());
        }
    }

    onServiceChange() {
        const serviceId = this.serviceSelect.value;

        if (serviceId && this.serviceData[serviceId]) {
            this.updateServiceInfo();
            this.updateTimeConstraints();
            this.updateBookingTimeInfo();
            this.checkAvailability();
        } else {
            this.hideServiceInfo();
            this.resetTimeConstraints();
        }

        this.updateTotalPrice();
    }

    onDateChange() {
        this.updateTimeConstraints();
        this.updateBookingTimeInfo();
        if (this.serviceSelect.value && this.startTimeInput.value) {
            this.checkAvailability();
        }
    }

    onTimeChange() {
        this.updateEndTime();
        this.updateBookingTimeInfo();
        if (this.serviceSelect.value && this.bookingDateInput.value) {
            this.checkAvailability();
        }
    }

    updateServiceInfo() {
        const serviceId = this.serviceSelect.value;
        const service = this.serviceData[serviceId];

        if (!this.serviceInfo) return;

        this.serviceInfo.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <div class="d-flex justify-content-between">
                        <div>
                            <h6 class="card-title">${service.name}</h6>
                            <p class="card-text text-muted">${service.description}</p>
                            <div class="d-flex gap-2">
                                <span class="badge bg-info">${this.formatDuration(service.duration)}</span>
                                <span class="badge bg-secondary">до ${service.max_capacity} чел.</span>
                                ${service.min_booking_hours > 0 ?
                                    `<span class="badge bg-warning">Бронировать за ${service.min_booking_hours} ч.</span>` :
                                    ''}
                            </div>
                        </div>
                        <div class="text-end">
                            <div class="text-success fw-bold fs-5">${service.price} руб.</div>
                            <small class="text-muted">за 1 чел.</small>
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.serviceInfo.style.display = 'block';
    }

    updateTimeConstraints() {
        const serviceId = this.serviceSelect.value;
        if (!serviceId || !this.serviceData[serviceId]) return;

        const service = this.serviceData[serviceId];
        const now = new Date();

        if (service.min_booking_hours > 0) {
            // Рассчитываем минимальное доступное время
            const minDatetime = new Date(now.getTime() + (service.min_booking_hours * 60 * 60 * 1000));
            const minDate = minDatetime.toISOString().split('T')[0];

            // Устанавливаем минимальную дату
            this.bookingDateInput.min = minDate;

            // Если выбрана сегодняшняя дата, устанавливаем минимальное время
            if (this.bookingDateInput.value === minDate) {
                // Рассчитываем минимальное время с округлением до 15 минут
                let minHour = minDatetime.getHours();
                let minMinute = minDatetime.getMinutes();

                // Округляем до ближайших 15 минут в большую сторону
                minMinute = Math.ceil(minMinute / 15) * 15;
                if (minMinute >= 60) {
                    minHour += 1;
                    minMinute = 0;
                }

                const minTime = `${minHour.toString().padStart(2, '0')}:${minMinute.toString().padStart(2, '0')}`;
                this.startTimeInput.min = minTime;

                // Если текущее выбранное время меньше минимального, сбрасываем его
                if (this.startTimeInput.value && this.startTimeInput.value < minTime) {
                    this.startTimeInput.value = minTime;
                }
            } else {
                // Для будущих дат снимаем ограничение по времени
                this.startTimeInput.min = '00:00';
            }
        }
    }

    updateBookingTimeInfo() {
        const serviceId = this.serviceSelect.value;
        if (!serviceId || !this.serviceData[serviceId] ||
            !this.bookingDateInput.value || !this.startTimeInput.value) {
            if (this.bookingTimeInfo) {
                this.bookingTimeInfo.style.display = 'none';
            }
            return;
        }

        const service = this.serviceData[serviceId];
        const selectedDatetime = new Date(`${this.bookingDateInput.value}T${this.startTimeInput.value}`);
        const now = new Date();

        if (!this.bookingTimeInfo) return;

        let message = '';
        let isAvailable = true;

        if (service.min_booking_hours > 0) {
            const minBookingDatetime = new Date(now.getTime() + (service.min_booking_hours * 60 * 60 * 1000));

            if (selectedDatetime < minBookingDatetime) {
                isAvailable = false;
                const minTimeStr = minBookingDatetime.toLocaleString('ru-RU', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
                message = `
                    <div class="text-danger">
                        <i class="fas fa-exclamation-triangle"></i>
                        <strong>Это время пока недоступно для бронирования.</strong><br>
                        <small>Можно будет забронировать после ${minTimeStr}</small>
                    </div>
                `;
            } else {
                const selectedTimeStr = selectedDatetime.toLocaleString('ru-RU', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
                message = `
                    <div class="text-success">
                        <i class="fas fa-check-circle"></i>
                        <strong>Это время доступно для бронирования.</strong><br>
                        <small>Выбрано: ${selectedTimeStr}</small>
                    </div>
                `;
            }
        } else {
            const selectedTimeStr = selectedDatetime.toLocaleString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            message = `
                <div class="text-success">
                    <i class="fas fa-check-circle"></i>
                    <strong>Эта услуга доступна для бронирования в любое время.</strong><br>
                    <small>Выбрано: ${selectedTimeStr}</small>
                </div>
            `;
        }

        this.bookingTimeInfo.innerHTML = `
            <div class="d-flex">
                <div class="me-3">
                    <i class="fas fa-clock"></i>
                </div>
                <div>
                    <h6 class="alert-heading mb-1">Информация о бронировании</h6>
                    ${message}
                    ${!isAvailable ? `
                    <div class="mt-2">
                        <button type="button" class="btn btn-sm btn-outline-primary" onclick="bookingForm.suggestNearestTime()">
                            <i class="fas fa-magic"></i> Предложить ближайшее доступное время
                        </button>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
        this.bookingTimeInfo.style.display = 'block';
        this.bookingTimeInfo.className = `alert ${isAvailable ? 'alert-info' : 'alert-warning'}`;
    }

    suggestNearestTime() {
        const serviceId = this.serviceSelect.value;
        if (!serviceId || !this.serviceData[serviceId]) return;

        const service = this.serviceData[serviceId];
        const now = new Date();

        // Рассчитываем ближайшее доступное время
        const minDatetime = new Date(now.getTime() + (service.min_booking_hours * 60 * 60 * 1000));

        // Округляем до ближайших 30 минут
        let hour = minDatetime.getHours();
        let minute = minDatetime.getMinutes();
        minute = Math.ceil(minute / 30) * 30;
        if (minute >= 60) {
            hour += 1;
            minute = 0;
        }
        if (hour >= 24) {
            hour = 0;
            minDatetime.setDate(minDatetime.getDate() + 1);
        }

        // Устанавливаем значения
        const dateStr = minDatetime.toISOString().split('T')[0];
        const timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;

        this.bookingDateInput.value = dateStr;
        this.startTimeInput.value = timeStr;

        // Обновляем форму
        this.onDateChange();
        this.onTimeChange();
    }

    updateEndTime() {
        // ... существующая логика расчета времени окончания ...
    }

    updateTotalPrice() {
        // ... существующая логика расчета стоимости ...
    }

    checkAvailability() {
        // ... существующая логика проверки доступности ...
    }

    formatDuration(minutes) {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;

        if (hours > 0 && mins > 0) {
            return `${hours} ч ${mins} мин`;
        } else if (hours > 0) {
            return `${hours} ч`;
        } else {
            return `${mins} мин`;
        }
    }

    hideServiceInfo() {
        if (this.serviceInfo) {
            this.serviceInfo.style.display = 'none';
        }
    }

    resetTimeConstraints() {
        if (this.bookingDateInput) {
            this.bookingDateInput.min = new Date().toISOString().split('T')[0];
        }
        if (this.startTimeInput) {
            this.startTimeInput.min = '00:00';
        }
    }

    updateForm() {
        if (this.serviceSelect.value) {
            this.onServiceChange();
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    window.bookingForm = new ServiceBookingForm();
});