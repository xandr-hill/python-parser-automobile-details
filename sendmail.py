import smtplib
from email.message import EmailMessage

def send_email(subject, body):
    # Визначте параметри вашого облікового запису електронної пошти
    sender_email = "your_email_address"
    receiver_email = "your_email_address"
    email_password = "your_email_password"

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    # Встановити сервер
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, email_password)

        # Надіслати повідомлення
        server.send_message(msg)

        # Закритиє сервер
        server.quit()

        print("Надіслано успішне сповіщення электронної пошти про завершення роботи скрипту.")

    except Exception as e:
        print(f"Помилка при надсиланні електронної пошти: {e}")


# <... Ваш код скрипта парсера може бути тут...>

# Наприклад, у разі завершення успішно
print("Скрипт парсера успішно завершив роботу.")

# Надіслати електронне сповіщення
send_email(
    subject="Завершення роботи скрипту парсера",
    body="Це сповіщення повідомляє Вам, що скрипт парсера успішно завершив роботу."
)