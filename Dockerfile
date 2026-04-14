FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y default-libmysqlclient-dev pkg-config gcc wget
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY . .
RUN rm -f Conceptos/dashboard_standalone.html Historico/dashboard_standalone.html
RUN wget -qO Conceptos/dashboard_standalone.html "https://github.com/Edwin1078/Portal/raw/master/Conceptos/dashboard_standalone.html"
RUN wget -qO Historico/dashboard_standalone.html "https://github.com/Edwin1078/Portal/raw/master/Historico/dashboard_standalone.html"
WORKDIR /app/backend
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

EXPOSE 8000
