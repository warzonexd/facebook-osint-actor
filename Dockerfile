FROM apify/actor-python:3.13

COPY requirements.txt ./

RUN echo "Python version:" \
 && python --version \
 && echo "Pip version:" \
 && pip --version \
 && pip install --no-cache-dir -r requirements.txt \
 && playwright install chromium

COPY . ./

CMD ["python", "-m", "my_actor.main"]
