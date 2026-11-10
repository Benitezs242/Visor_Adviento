FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY monitor_adviento.py web_alerta.py ./
# El hosting define PORT; la configuración (clave, WhatsApp...) va en variables de entorno.
CMD ["python", "-u", "web_alerta.py"]
