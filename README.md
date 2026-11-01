# Deploying Second Django ASGI Application with Daphne & Nginx

This guide documents deployment of the second Django application on the
same Ubuntu VM where the first application is already running.

## Application Configuration

  Property                    Value
  --------------------------- -------------------------------------
  Application                 Bhujan Matrimony
  Project Directory           `/home/ubuntu/Applications/GautamGeeks`
  Virtual Environment         `/home/ubuntu/Applications/bhujanMatrimony/venv`
  Django Project Package      `gautamgeeks`
  Internal Daphne Port        `8001`
  Domain                      `gautamgeeks.gautamankul.site`
  Existing Application Port   `8001`

The first application continues to use port `8001`. The second
application uses port `8001`.

------------------------------------------------------------------------

## 1. Verify the Second Django Application

Go to the project directory:

``` bash
cd /home/ubuntu/Applications/GautamGeeksAPI
source venv/bin/activate
```

Run Django checks:

``` bash
python manage.py check
```

If the check is successful, test Daphne manually:

``` bash
daphne -b 127.0.0.1 -p 8001 gautamgeeks.asgi:application
```

From another terminal, test the local application:

``` bash
curl http://127.0.0.1:8001
```

If the application responds correctly, stop Daphne with:

``` text
Ctrl + C
```

------------------------------------------------------------------------

## 2. Configure Django Settings

Open the second application's `settings.py`.

Set production settings similar to:

``` python
DEBUG = False

ALLOWED_HOSTS = [
    "gautamgeeks.gautamankul.site",
    "68.233.111.242",
    "127.0.0.1",
    "localhost",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
```

Make sure the Django project package and ASGI configuration match the
actual project structure.

------------------------------------------------------------------------

## 3. Create a Separate Daphne Systemd Service

Do not modify the existing `daphne.service` used by the first
application.

Create a new service:

``` bash
sudo nano /etc/systemd/system/daphne.service
```

Add:

``` ini
[Unit]
Description=Daphne ASGI Server for Gautam Geeks
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/Applications/GautamGeeksAPI
Environment="DJANGO_SETTINGS_MODULE=gautamgeeks.settings"
ExecStart=/home/ubuntu/Applications/GautamGeeksAPI/venv/bin/daphne -b 127.0.0.1 -p 8001 gautamgeeks.asgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Save and exit.

Reload systemd:

``` bash
sudo systemctl daemon-reload
```

Enable the service at boot:

``` bash
sudo systemctl enable daphne
```

Start the service:

``` bash
sudo systemctl start daphne
```

Check the service:

``` bash
sudo systemctl status daphne
```

View recent logs:

``` bash
journalctl -u daphne -n 50 --no-pager
```

Follow logs continuously:

``` bash
journalctl -u daphne -f
```

------------------------------------------------------------------------

## 4. Configure DNS

Create a DNS A record for the second application from Namecheap.com.

Example:

  Property   Value
  ---------- ------------------------------
  Type       `A`
  Host       `matrimony`
  Value      `129.225.93.54`
  Result     `gautamgeeks.gautamankul.site`

After DNS propagation, verify:

``` bash
nslookup gautamgeeks.gautamankul.site
```

The domain should resolve to:

``` text
68.233.111.242
```

------------------------------------------------------------------------

## 5. Create the Second Nginx Configuration

Create a new Nginx site:

``` bash
sudo nano /etc/nginx/sites-available/gautamgeeks
```

Add:

``` nginx
server {
    listen 80;
    server_name gautamgeeks.gautamankul.site;

    location / {
        proxy_pass http://127.0.0.1:8001;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8001;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 86400;
    }
}
```

The First application uses port `8001`, while the second application remains on port `8002`.

------------------------------------------------------------------------

## 6. Enable the First Nginx Site

Create the symbolic link:

``` bash
sudo ln -s /etc/nginx/sites-available/gautamgeeks /etc/nginx/sites-enabled/
```

Test Nginx configuration:

``` bash
sudo nginx -t
```

If the test is successful, reload Nginx:

``` bash
sudo systemctl reload nginx
```

Test HTTP:

``` bash
curl -I http://gautamgeeks.gautamankul.site
```

Or open:

``` text
http://gautamgeeks.gautamankul.site
```

------------------------------------------------------------------------

## 7. Configure SSL with Certbot

After HTTP is working, install Certbot if it is not already installed:

``` bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

Request an SSL certificate for the second domain:

``` bash
sudo certbot --nginx -d gautamgeeks.gautamankul.site
```

Test Nginx:

``` bash
sudo nginx -t
```

Reload Nginx:

``` bash
sudo systemctl reload nginx
```

Test HTTPS:

``` bash
curl -I https://gautamgeeks.gautamankul.site/
```

The application should now be available at:

``` text
https://matrimony.gautamankul.site
```

------------------------------------------------------------------------

## 8. Final Architecture

Both applications run on the same VM:

``` text
                         INTERNET
                            |
                    68.233.111.242
                            |
                          NGINX
                       /          \
                      /            \
       api.gautamankul.site     matrimony.gautamankul.site
               |                         |
               v                         v
       127.0.0.1:8000             127.0.0.1:8001
               |                         |
               v                         v
       daphne.service          daphne-bhujan.service
               |                         |
               v                         v
       /home/ubuntu/kaamdekho   /home/ubuntu/bhujanMatrimony
```

## 9. Important Commands

### Check both Daphne services

``` bash
sudo systemctl status daphne
sudo systemctl status daphne-bhujan
```

### Restart the second application

``` bash
sudo systemctl restart daphne-bhujan
```

### Stop the second application

``` bash
sudo systemctl stop daphne-bhujan
```

### Start the second application

``` bash
sudo systemctl start daphne-bhujan
```

### View second application logs

``` bash
journalctl -u daphne-bhujan -n 100 --no-pager
```

### Check Nginx

``` bash
sudo nginx -t
sudo systemctl status nginx
```

### Reload Nginx after configuration changes

``` bash
sudo systemctl reload nginx
```

------------------------------------------------------------------------

## 10. Troubleshooting

### Daphne service is not running

Check:

``` bash
sudo systemctl status daphne-bhujan
```

Then:

``` bash
journalctl -u daphne-bhujan -n 100 --no-pager
```

Common things to verify:

-   Correct `WorkingDirectory`
-   Correct virtual environment path
-   Correct `DJANGO_SETTINGS_MODULE`
-   Correct `asgi:application` module
-   Port `8001` is not already in use

Check port:

``` bash
sudo ss -lntp | grep 8001
```

### Nginx returns 502 Bad Gateway

Check whether Daphne is listening:

``` bash
sudo ss -lntp | grep 8001
```

Then:

``` bash
curl http://127.0.0.1:8001
```

If this fails, check the Daphne service first.

Then check Nginx logs:

``` bash
sudo tail -f /var/log/nginx/error.log
```

### Domain does not open

Verify DNS:

``` bash
nslookup matrimony.gautamankul.site
```

Verify Nginx:

``` bash
sudo nginx -t
```

Verify the service:

``` bash
sudo systemctl status daphne-bhujan
```

------------------------------------------------------------------------

## 11. Deployment Rule for Additional Applications

For every additional Django application on the same VM, assign a unique
internal port.

Example:

  Application           Daphne Port
  ------------------- -------------
  `kaamdekho`                `8000`
  `bhujanMatrimony`          `8001`
  Application 3              `8002`
  Application 4              `8003`

Each application should have:

1.  Its own project directory.
2.  Its own virtual environment.
3.  Its own Daphne systemd service.
4.  Its own internal port.
5.  Its own Nginx `server` block.
6.  Its own domain/subdomain.

Nginx can then route each domain to the appropriate local Daphne port.

------------------------------------------------------------------------

## 12. Firewall

No additional public port such as `8001` needs to be exposed to the
internet when Nginx is proxying to `127.0.0.1:8001`.

Keep public access through:

``` text
80  -> HTTP
443 -> HTTPS
```

Daphne remains private on:

``` text
127.0.0.1:8001
```

This allows Nginx to handle public HTTP/HTTPS traffic while Daphne only
accepts local connections.

## Usefull commands

1. Daphne Service to sees how many daphne services running

```bash
systemctl list-units --type=service --state=running | grep -i daphne
sudo systemctl status daphne
sudo systemctl status daphne-bhujan
```

- stop all the services
```bash
sudo systemctl stop daphne
```

- start all the services
```bash
sudo systemctl restart daphne.service
sudo systemctl start daphne

```

2. Nginx status
```bash
sudo systemctl status nginx
sudo systemctl restart nginx
sudo systemctl reload nginx
sudo systemctl status nginx
```

3. Check Port
```bash
sudo ss -lntp | grep 8001
sudo ss -lntp | grep 8000
```
## After new changes 

1. After changing your Django code:

```
sudo systemctl restart daphne.service
```

Check whether it started successfully:

2. If you changed `/etc/systemd/system/daphne.service` itself, run:

```aiignore
sudo systemctl status daphne.service
```

and

```aiignore
sudo systemctl daemon-reload
sudo systemctl restart daphne.service
```
To check for errors:

```aiignore
sudo journalctl -u daphne.service -f
```
