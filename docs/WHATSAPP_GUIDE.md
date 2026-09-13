# IP-SAKTI Sahayak — Complete WhatsApp Setup Guide (From Scratch)

This guide walks you through setting up the WhatsApp interface for **IP-SAKTI Sahayak** from absolute scratch, with zero prior setup or paid subscriptions.

---

## What You Need Before Starting

1. **A phone with WhatsApp installed** (your normal personal WhatsApp is fine).
2. **A free Twilio account** (no credit card needed).
3. **ngrok** (free tool that lets Twilio reach your local computer).

---

## Step 1: Create a Free Twilio Account

1. Go to **[https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio)**.
2. Sign up with your email and set a password.
3. Verify your email address.
4. When asked for a phone number to verify, enter your personal mobile number and submit the verification SMS code.
5. On the onboarding questions, select:
   - *Which Twilio product are you here to use?* ➔ **SMS / WhatsApp**
   - *What do you plan to build?* ➔ **Bot / AI Assistant**
   - *Preferred language?* ➔ **Python**
6. You will land on the **Twilio Console Dashboard**.

> **IMPORTANT:** You will see prompts like *"Upgrade Account"* or *"Buy a Phone Number"*. **DO NOT click them.** You do not need to buy any number. Twilio gives you a free WhatsApp Sandbox number.

---

## Step 2: Get Your Twilio Credentials

On the Twilio Console homepage ([https://console.twilio.com](https://console.twilio.com)):

1. Look under **Account Info** in the middle of the screen.
2. You will see:
   - **Account SID:** Starts with `AC...` (Click the copy icon).
   - **Auth Token:** Click **"Show"** or the eye icon to reveal it, then copy it.
3. Open your project's `.env` file and paste them at the bottom:

```env
TWILIO_ACCOUNT_SID=AC_YOUR_TWILIO_ACCOUNT_SID_HERE
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

*(Save the `.env` file).*

---

## Step 3: Connect Your Phone to the WhatsApp Sandbox

1. Open this link directly in your browser:  
   👉 **[https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn](https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn)**
2. In the box labeled **"Connect to WhatsApp Sandbox"**, you will see:
   - A sandbox phone number: typically `+1 415 523 8886`.
   - A unique join code for your account: e.g. `join bar-greatly` (or whatever word is shown for you).
   - A **QR Code** displayed on the screen.
3. **Open WhatsApp on your mobile phone**:
   - Option A: Scan the QR code on your monitor using your phone camera. It will open WhatsApp with the text `join bar-greatly` already typed in.
   - Option B: Save `+1 415 523 8886` as a contact named "Twilio Sandbox" and send the message `join bar-greatly`.
4. **Hit Send in WhatsApp**.
5. Within 5 seconds, Twilio will send you an automated reply:
   > *"You are all set! The sandbox is active..."*
6. Your phone is now officially connected!

---

## Step 4: Install and Run ngrok (Expose Port 8000)

Because your backend runs on your local computer (`http://localhost:8000`), Twilio's cloud needs a public URL to send incoming messages to. `ngrok` creates this secure bridge.

### 4.1 Install ngrok (if not already installed)
Open a Windows PowerShell terminal and run:
```powershell
winget install ngrok
```
*(Or download the `.exe` from [ngrok.com](https://ngrok.com)).*

### 4.2 Start the ngrok tunnel
Open a **new separate terminal** (keep your `uvicorn` backend running in the first terminal) and type:
```powershell
ngrok http 8000
```
You will see output like this:
```text
Session Status                online
Forwarding                    https://mural-rentable-outlast.ngrok-free.dev -> http://localhost:8000
```

> 💡 **Your Domain is Permanent:**  
> `mural-rentable-outlast.ngrok-free.dev` is your registered free static dev domain on ngrok.  
> This means whenever you run `ngrok http 8000`, it will **always** use this same link, so you never have to change your Twilio webhook URL again!

---

## Step 5: Configure the Webhook in Twilio

1. Go directly to the Sandbox Settings page:  
   👉 **[https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox](https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox)**
2. Look for the row that says **"WHEN A MESSAGE COMES IN"**.
3. In that text field, paste your ngrok URL with `/whatsapp/webhook` added at the end.  
   **Example:**
   ```text
   https://mural-rentable-outlast.ngrok-free.dev/whatsapp/webhook
   ```
4. Set the HTTP Method dropdown to **`POST`**.
5. Leave the "Status callback URL" blank.
6. Scroll down and click the blue **Save** button.

---

## Step 6: Test IP-SAKTI Live on WhatsApp!

1. Open WhatsApp on your phone in the conversation with `+1 415 523 8886`.
2. Send a query, for example:
   > *What is Section 3(p) of the Patents Act?*
3. Within seconds, you will receive a grounded response from IP-SAKTI citing relevant traditional knowledge guidelines and clauses!
4. Send a follow-up question:
   > *What are the exceptions to this rule?*
5. IP-SAKTI remembers your previous question using its SQLite session memory (`wa_...`) and answers in context!

---

## Step 7: How Others Can Chat with Your Bot (QR Code)

Anyone who wants to use IP-SAKTI on WhatsApp can connect in seconds:

1. **Website Button:** On the IP-SAKTI web page (`frontend/index.html` or `http://localhost:8000/`), click the green **WhatsApp** button in the top navigation bar.
2. A modal pops up with a QR code and instructions.
3. The visitor scans the QR code with their phone camera.
4. WhatsApp opens automatically with the message `join bar-greatly` pre-typed.
5. They hit **Send** once to activate their chat, and then start asking any Ayurveda IP questions!

Direct link for mobile users:
👉 **[https://wa.me/14155238886?text=join%20bar-greatly](https://wa.me/14155238886?text=join%20bar-greatly)**

---

## Limits & Maintenance

| Situation | Explanation | Solution |
|---|---|---|
| **72-hour inactivity** | Twilio free sandbox disconnects after 72 hours of no messages. | Send `join bar-greatly` once to reconnect. |
| **ngrok restarted** | If ngrok was restarted without a static domain, the public URL changes. | Paste the new ngrok URL into Twilio Sandbox Settings and hit Save. |
| **Message character limit** | WhatsApp single bubble limit is 1,600 characters. | `src/whatsapp.py` automatically trims long replies with `[…reply truncated]`. |
| **Cost** | 100% Free on the Twilio trial sandbox. | Never click "Upgrade" or "Buy Number". |

---

## Troubleshooting Checklist

1. **I sent a message on WhatsApp but got no reply:**
   - Check the **ngrok terminal**: Do you see a `POST /whatsapp/webhook 200 OK` line appear when you send a message?
   - If not, verify that the webhook URL in Twilio ends with `/whatsapp/webhook` and method is `POST`.
   - Ensure your `uvicorn` backend is running on port 8000.
2. **Twilio replied with *"Your sandbox session has expired"*:*
   - Simply reply `join bar-greatly` to reactivate.
3. **Server error / 500:**
   - Check the uvicorn terminal output for any traceback. The bot automatically handles timeouts and retries.
