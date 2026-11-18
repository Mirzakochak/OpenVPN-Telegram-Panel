<div align="center">

# 🛡 OpenVPN Telegram Management Panel
### پنل پیشرفته و تمام‌خودکار مدیریت OpenVPN از طریق ربات تلگرام

[![OS](https://img.shields.io/badge/OS-Ubuntu%20%7C%20Debian-orange?style=for-the-badge&logo=linux)](https://ubuntu.com/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![OpenVPN](https://img.shields.io/badge/OpenVPN-Optimized-green?style=for-the-badge&logo=openvpn)](https://openvpn.net/)
[![Telegram](https://img.shields.io/badge/Telegram-Inline%20Bot-2CA5E0?style=for-the-badge&logo=telegram)](https://telegram.org/)

**نصب و راه‌اندازی کامل سرور OpenVPN به همراه ربات مدیریت کاربران با منوی شیشه‌ای، آمار مصرف ترافیک، محدودیت کاربر همزمان و سیستم انقضای خودکار تنها با یک دستور!**

</div>

---

## ✨ ویژگی‌ها و امکانات کلیدی

### 🚀 بهینه‌سازی‌های سمت سرور (OpenVPN)
* **تک‌فایل اتصال عمومی (Universal `.ovpn`):** بدون نیاز به ساخت فایل جداگانه برای هر مشتری؛ احراز هویت بر پایه **نام کاربری و رمز عبور** انجام می‌شود.
* **سرعت و پایداری حداکثری:** استفاده از الگوریتم‌های رمزنگاری مدرن `AES-128-GCM` و `CHACHA20-POLY1305` به همراه تنظیمات `MTU 1420` و `MSSFIX 1380` برای جلوگیری از افت سرعت و قطعی در شبکه‌های موبایل.
* **جلوگیری از نشت DNS:** فعال‌سازی کامل `redirect-gateway` و `block-outside-dns`.
* **پشتیبانی از دامنه و ساب‌دامنه:** امکان اتصال از طریق IP مستقیم یا ساب‌دامنه اختصاصی.
* **مدیریت لحظه‌ای نشست‌ها (`Management Interface`):** امکان قطع فوری اتصال کاربر در هر لحظه بدون نیاز به ری‌استارت سرویس.

### 🤖 امکانات پنل مدیریتی تلگرام
* **منوی تمام شیشه‌ای (Inline Keyboard):** مدیریت ۱۰۰٪ گرافیکی و بدون نیاز به تایپ دستورات پیچیده.
* **ساخت سریع اشتراک:** قابلیت تولید رمز عبور تصادفی خودکار و ارسال پیام آماده فوروارد به مشتری به همراه فایل اتصال.
* **محدودیت تعداد دستگاه همزمان:** جلوگیری از اشتراک‌گذاری اکانت توسط کاربران (قابل تنظیم به صورت اختصاصی برای هر کاربر از ۱ تا ۵ دستگاه).
* **آمار دقیق مصرف ترافیک (Traffic Accounting):** ثبت دائمی میزان دانلود و آپلود هر کاربر حتی پس از قطع اتصال و ری‌استارت سرور، به همراه قابلیت ریست کردن حجم.
* **مشاهده کاربران آنلاین:** نمایش IP واقعی، زمان اتصال و میزان مصرف لحظه‌ای کاربران متصل به سرور.
* **سیستم انقضا و هشدار خودکار (Cronjob):** بررسی روزانه تاریخ انقضای اکانت‌ها، ارسال هشدار ۲ روز قبل از اتمام اشتراک و حذف خودکار کاربران منقضی‌شده.
* **پشتیبان‌گیری یک‌کلیکی (Backup):** دریافت فایل فشرده `ZIP` از کل تنظیمات و دیتابیس کاربران در تلگرام.

---

## 💻 پیش‌نیازها

* یک سرور مجازی (VPS) با سیستم‌عامل **Ubuntu (20.04 / 22.04 / 24.04)** یا **Debian (10 / 11 / 12)**
* دسترسی **Root** به سرور
* یک ربات تلگرام ساخته شده در [@BotFather](https://t.me/BotFather) (دریافت `Bot Token`)
* آیدی عددی اکانت تلگرام ادمین (قابل دریافت از [@userinfobot](https://t.me/userinfobot))

---

## ⚡ نصب سریع (تک‌خطی)

وارد محیط SSH سرور خود شوید و دستور زیر را اجرا کنید:

```bash
bash <(curl -Ls [https://raw.githubusercontent.com/Mirzakochak/OpenVPN-Telegram-Panel/main/install.sh](https://raw.githubusercontent.com/Mirzakochak/OpenVPN-Telegram-Panel/main/install.sh))
