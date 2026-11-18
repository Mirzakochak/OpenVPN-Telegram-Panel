#!/bin/bash

# بررسی دسترسی روت
if [[ "$EUID" -ne 0 ]]; then
	echo "لطفاً این اسکریپت را با دسترسی root اجرا کنید (sudo bash install.sh)"
	exit 1
fi

if [[ ! -e /dev/net/tun ]] || ! ( exec 7<>/dev/net/tun ) 2>/dev/null; then
	echo "دستگاه TUN در سرور شما فعال نیست."
	exit 1
fi

# تشخیص سیستم عامل
if grep -qs "ubuntu" /etc/os-release; then
	os="ubuntu"
elif [[ -e /etc/debian_version ]]; then
	os="debian"
else
	echo "این اسکریپت فقط از Ubuntu و Debian پشتیبانی می‌کند."
	exit 1
fi

# اگر قبلاً نصب شده باشد، منوی مدیریت سریع باز می‌شود
if [[ -e /etc/openvpn/server/server.conf ]]; then
    clear
    echo "=========================================================="
    echo "   مدیریت سریع پنل OpenVPN و ربات تلگرام"
    echo "=========================================================="
    echo "   1) تغییر توکن ربات و آیدی عددی ادمین"
    echo "   2) ری‌استارت کردن ربات تلگرام"
    echo "   3) ری‌استارت کردن سرویس OpenVPN"
    echo "   4) حذف کامل OpenVPN و ربات"
    echo "   5) خروج"
    read -p "انتخاب شما [1-5]: " menu_opt < /dev/tty
    case "$menu_opt" in
        1)
            read -p "توکن جدید ربات تلگرام: " NEW_TOKEN < /dev/tty
            read -p "آیدی عددی جدید ادمین: " NEW_ADMIN < /dev/tty
            cat << EOF > /opt/openvpn-bot/config.py
TOKEN = '$NEW_TOKEN'
ADMIN_ID = $NEW_ADMIN
CONFIG_PATH = '/opt/openvpn-bot/Universal-Client.ovpn'
EOF
            systemctl restart openvpn-bot.service
            echo "✅ تنظیمات جدید ذخیره و ربات ری‌استارت شد."
            ;;
        2)
            systemctl restart openvpn-bot.service
            echo "✅ ربات تلگرام ری‌استارت شد."
            ;;
        3)
            systemctl restart openvpn-server@server.service
            echo "✅ سرویس OpenVPN ری‌استارت شد."
            ;;
        4)
            read -p "آیا از حذف کامل مطمئن هستید؟ [y/N]: " confirm < /dev/tty
            if [[ "$confirm" =~ ^[yY]$ ]]; then
                systemctl disable --now openvpn-bot.service openvpn-server@server.service openvpn-iptables.service
                apt-get remove --purge -y openvpn
                rm -rf /etc/openvpn /opt/openvpn-bot /etc/systemd/system/openvpn-bot.service /etc/systemd/system/openvpn-iptables.service
                systemctl daemon-reload
                echo "🗑 همه‌چیز به طور کامل حذف شد."
            fi
            ;;
        *)
            exit 0
            ;;
    esac
    exit 0
fi

clear
echo "=========================================================="
echo "   نصب‌کننده هوشمند OpenVPN + پنل مدیریتی ربات تلگرام   "
echo "=========================================================="
echo ""

# دریافت اجباری از کیبورد کاربر با استفاده از < /dev/tty
read -p "1️⃣ توکن ربات تلگرام (Bot Token) را وارد کنید: " BOT_TOKEN < /dev/tty
while [[ -z "$BOT_TOKEN" ]]; do
    read -p "❌ توکن نمی‌تواند خالی باشد! لطفاً توکن را وارد کنید: " BOT_TOKEN < /dev/tty
done

read -p "2️⃣ آیدی عددی ادمین تلگرام (Admin Numeric ID) را وارد کنید: " ADMIN_ID < /dev/tty
while [[ ! "$ADMIN_ID" =~ ^[0-9]+$ ]]; do
    read -p "❌ آیدی عددی نامعتبر است! فقط عدد وارد کنید: " ADMIN_ID < /dev/tty
done

# تشخیص IP عمومی سرور
ip=$(ip -4 addr | grep inet | grep -vE '127(\.[0-9]{1,3}){3}' | cut -d '/' -f 1 | grep -oE '[0-9]{1,3}(\.[0-9]{1,3}){3}' | head -n 1)
if echo "$ip" | grep -qE '^(10\.|172\.1[6789]\.|172\.2[0-9]\.|172\.3[01]\.|192\.168)'; then
	ip=$(wget -T 10 -t 1 -4qO- "http://ip1.dynupdate.no-ip.com/" || curl -m 10 -4Ls "http://ip1.dynupdate.no-ip.com/")
fi

echo ""
read -p "3️⃣ دامنه یا ساب‌دامنه (خالی بگذارید تا از IP سرور [$ip] استفاده شود): " custom_domain < /dev/tty
[[ -z "$custom_domain" ]] && config_ip="$ip" || config_ip="$custom_domain"

echo ""
echo "4️⃣ پروتکل اتصال را انتخاب کنید:"
echo "   1) UDP (پیشنهادی برای سرعت بالا)"
echo "   2) TCP (پیشنهادی برای عبور از محدودیت‌ها - مثل پورت 443)"
read -p "انتخاب [1]: " protocol < /dev/tty
[[ "$protocol" == "2" ]] && protocol=tcp || protocol=udp

read -p "5️⃣ پورت OpenVPN [1194]: " port < /dev/tty
[[ -z "$port" ]] && port="1194"

echo ""
echo "⏳ در حال نصب پیش‌نیازها و پیکربندی سرور... لطفاً چند لحظه صبر کنید..."

apt-get update -y
apt-get install -y openvpn openssl ca-certificates wget curl python3 python3-pip python3-venv iptables zip

# نصب Easy-RSA
easy_rsa_url='https://github.com/OpenVPN/easy-rsa/releases/download/v3.2.6/EasyRSA-3.2.6.tgz'
mkdir -p /etc/openvpn/server/easy-rsa/
{ wget -qO- "$easy_rsa_url" 2>/dev/null || curl -sL "$easy_rsa_url" ; } | tar xz -C /etc/openvpn/server/easy-rsa/ --strip-components 1
chown -R root:root /etc/openvpn/server/easy-rsa/
cd /etc/openvpn/server/easy-rsa/

./easyrsa --batch init-pki
./easyrsa --batch build-ca nopass
./easyrsa gen-tls-crypt-key
./easyrsa --batch --days=3650 build-server-full server nopass
./easyrsa --batch build-client-full universal nopass

cp pki/ca.crt pki/issued/server.crt pki/private/server.key /etc/openvpn/server
cp pki/private/easyrsa-tls.key /etc/openvpn/server/tc.key
openssl dhparam -out /etc/openvpn/server/dh.pem 2048

# پیدا کردن پلاگین PAM
pam_plugin=$(find /usr -type f -name 'openvpn-plugin-auth-pam.so' | head -n 1)
echo "account required pam_unix.so" > /etc/pam.d/openvpn
echo "auth required pam_unix.so" >> /etc/pam.d/openvpn

# ساخت فایل کانفیگ بهینه‌شده سرور
cat << EOF > /etc/openvpn/server/server.conf
local $ip
port $port
proto $protocol
dev tun
ca ca.crt
cert server.crt
key server.key
dh dh.pem
auth SHA512
tls-crypt tc.key
data-ciphers AES-128-GCM:CHACHA20-POLY1305:AES-256-GCM
tun-mtu 1420
mssfix 1380
topology subnet
server 10.8.0.0 255.255.255.0
push "dhcp-option DNS 1.1.1.1"
push "dhcp-option DNS 8.8.8.8"
push "redirect-gateway def1 bypass-dhcp"
push "block-outside-dns"
keepalive 10 60
persist-key
persist-tun
verb 3
plugin $pam_plugin openvpn
verify-client-cert none
username-as-common-name
duplicate-cn
script-security 2
client-connect /etc/openvpn/server/limit.sh
status /etc/openvpn/server/openvpn-status.log 5
management 127.0.0.1 7505
EOF

[[ "$protocol" = "udp" ]] && echo "explicit-exit-notify" >> /etc/openvpn/server/server.conf

# اسکریپت محدودیت اتصال همزمان
cat << 'EOF' > /etc/openvpn/server/limit.sh
#!/bin/bash
LIMIT_FILE="/etc/openvpn/server/user_limits.txt"
DEFAULT_LIMIT=2

USER_LIMIT=$DEFAULT_LIMIT
if [ -f "$LIMIT_FILE" ]; then
    CUSTOM=$(grep "^$common_name:" "$LIMIT_FILE" | cut -d':' -f2)
    if [[ -n "$CUSTOM" ]]; then
        USER_LIMIT=$CUSTOM
    fi
fi

if [ -f "/etc/openvpn/server/openvpn-status.log" ]; then
    COUNT=$(grep -c "^$common_name," /etc/openvpn/server/openvpn-status.log)
    if [ "$COUNT" -ge "$USER_LIMIT" ]; then
        exit 1
    fi
fi
exit 0
EOF
chmod +x /etc/openvpn/server/limit.sh
touch /etc/openvpn/server/user_limits.txt

# فعال‌سازی IP Forwarding و فایروال
echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-openvpn-forward.conf
echo 1 > /proc/sys/net/ipv4/ip_forward

iptables_path=$(command -v iptables)
cat << EOF > /etc/systemd/system/openvpn-iptables.service
[Unit]
After=network-online.target
[Service]
Type=oneshot
ExecStart=$iptables_path -w 5 -t nat -A POSTROUTING -s 10.8.0.0/24 ! -d 10.8.0.0/24 -j SNAT --to $ip
ExecStart=$iptables_path -w 5 -I INPUT -p $protocol --dport $port -j ACCEPT
ExecStart=$iptables_path -w 5 -I FORWARD -s 10.8.0.0/24 -j ACCEPT
ExecStop=$iptables_path -w 5 -t nat -D POSTROUTING -s 10.8.0.0/24 ! -d 10.8.0.0/24 -j SNAT --to $ip
ExecStop=$iptables_path -w 5 -D INPUT -p $protocol --dport $port -j ACCEPT
ExecStop=$iptables_path -w 5 -D FORWARD -s 10.8.0.0/24 -j ACCEPT
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF

systemctl enable --now openvpn-iptables.service

# ساخت فایل Universal-Client.ovpn
mkdir -p /opt/openvpn-bot
OVPN_PATH="/opt/openvpn-bot/Universal-Client.ovpn"

cat << EOF > "$OVPN_PATH"
client
dev tun
proto $protocol
remote $config_ip $port
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
auth SHA512
data-ciphers AES-128-GCM:CHACHA20-POLY1305:AES-256-GCM
tun-mtu 1420
mssfix 1380
ignore-unknown-option block-outside-dns
verb 3
auth-user-pass
<ca>
$(cat /etc/openvpn/server/ca.crt)
</ca>
<tls-crypt>
$(cat /etc/openvpn/server/tc.key)
</tls-crypt>
<cert>
$(sed -ne '/BEGIN CERTIFICATE/,$ p' /etc/openvpn/server/easy-rsa/pki/issued/universal.crt)
</cert>
<key>
$(cat /etc/openvpn/server/easy-rsa/pki/private/universal.key)
</key>
EOF

systemctl enable --now openvpn-server@server.service

# راه‌اندازی محیط مجازی پایتون و دانلود ربات
python3 -m venv /opt/openvpn-bot/venv
/opt/openvpn-bot/venv/bin/pip install pyTelegramBotAPI schedule

# ⚠️ نام کاربری و نام مخزن گیت‌هاب خود را در این خط جایگزین کنید ⚠️
GITHUB_RAW_URL="https://raw.githubusercontent.com/Mirzakochak/OpenVPN-Telegram-Panel/main/bot.py"
wget -qO /opt/openvpn-bot/bot.py "$GITHUB_RAW_URL"

# ذخیره توکن و آیدی عددی در config.py
cat << EOF > /opt/openvpn-bot/config.py
TOKEN = '$BOT_TOKEN'
ADMIN_ID = $ADMIN_ID
CONFIG_PATH = '$OVPN_PATH'
EOF

# ساخت سرویس systemd برای اجرای دائمی ربات
cat << EOF > /etc/systemd/system/openvpn-bot.service
[Unit]
Description=OpenVPN Telegram Management Bot
After=network.target openvpn-server@server.service

[Service]
User=root
WorkingDirectory=/opt/openvpn-bot
ExecStart=/opt/openvpn-bot/venv/bin/python /opt/openvpn-bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now openvpn-bot.service

clear
echo "=========================================================="
echo "✅ نصب با موفقیت کامل شد!"
echo "🤖 ربات تلگرام فعال شد. هم‌اکنون در ربات دستور /start را بزنید."
echo "📁 مسیر فایل کانفیگ: $OVPN_PATH"
echo "=========================================================="
