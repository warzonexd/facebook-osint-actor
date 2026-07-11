# Use Apify's Playwright base image which bundles Chromium and all required
# Linux shared libraries (libglib, libnss, libatk, etc.) so Playwright runs
# without missing shared object errors.
FROM apify/actor-python-playwright:3.13

COPY requirements.txt ./

RUN echo "Python version:" \
 && python --version \
 && echo "Pip version:" \
 && pip --version \
 && pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium

COPY . ./

CMD ["python", "-m", "my_actor.main"]
