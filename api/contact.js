// api/contact.js
//
// Vercel Serverless Function (Node.js runtime, автоматично разпознаваема
// от Vercel заради местоположението в папка /api — не е нужен package.json
// за това, стига да не добавяш външни npm пакети).
//
// Какво прави:
//   1. Проверява, че заявката идва от логнат потребител (Supabase JWT
//      токън в Authorization header).
//   2. Валидира съдържанието на съобщението.
//   3. Изпраща имейл до archipari888@gmail.com чрез Resend API, с
//      reply-to = имейла на потребителя (за да можеш просто да натиснеш
//      "Отговори" в пощата си).
//
// Изисква следните Environment Variables в настройките на Vercel проекта
// (Settings → Environment Variables) — виж AUTH_SETUP.md за инструкции:
//   SUPABASE_URL       - същият URL като в js/auth.js
//   SUPABASE_ANON_KEY  - същият anon key като в js/auth.js
//   RESEND_API_KEY     - таен API ключ от resend.com (НИКОГА във фронтенда!)

const CONTACT_RECEIVER_EMAIL = "archipari888@gmail.com";

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Методът не е позволен." });
  }

  const { SUPABASE_URL, SUPABASE_ANON_KEY, RESEND_API_KEY } = process.env;
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY || !RESEND_API_KEY) {
    console.error("Липсват Environment Variables (SUPABASE_URL/SUPABASE_ANON_KEY/RESEND_API_KEY).");
    return res.status(500).json({ error: "Сървърът не е конфигуриран правилно (липсват env vars)." });
  }

  // 1) Извличаме токъна от Authorization: Bearer <token>
  const authHeader = req.headers.authorization || "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null;
  if (!token) {
    return res.status(401).json({ error: "Трябва да си влязъл в акаунта си." });
  }

  // 2) Проверяваме токъна директно през Supabase REST API (без нужда от
  // допълнителна npm библиотека).
  let user;
  try {
    const userRes = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
      headers: {
        apikey: SUPABASE_ANON_KEY,
        Authorization: `Bearer ${token}`,
      },
    });
    if (!userRes.ok) {
      return res.status(401).json({ error: "Сесията е невалидна или е изтекла — влез отново." });
    }
    user = await userRes.json();
  } catch (err) {
    console.error("Грешка при проверка на потребителя:", err);
    return res.status(502).json({ error: "Неуспешна проверка на акаунта. Опитай отново." });
  }

  if (!user || !user.email) {
    return res.status(401).json({ error: "Невалиден акаунт." });
  }

  // 3) Валидация на съдържанието
  const { name, topic, message } = req.body || {};

  if (!message || typeof message !== "string" || message.trim().length < 3) {
    return res.status(400).json({ error: "Съобщението е твърде кратко." });
  }
  if (message.length > 5000) {
    return res.status(400).json({ error: "Съобщението е твърде дълго (макс. 5000 символа)." });
  }

  const safeName = (typeof name === "string" ? name : "").slice(0, 200) || "(без име)";
  const safeTopic = (typeof topic === "string" ? topic : "general").slice(0, 100);

  // 4) Изпращане на имейл чрез Resend
  try {
    const emailRes = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        // ЗАБЕЛЕЖКА: "onboarding@resend.dev" работи без верификация на
        // домейн, СТИГА получателят (CONTACT_RECEIVER_EMAIL) да е имейлът,
        // с който е регистриран Resend акаунтът. За изпращане към
        // произволни имейли по-късно ще трябва да верифицираш собствен
        // домейн в Resend (виж AUTH_SETUP.md).
        from: "ArchiPari контактна форма <onboarding@resend.dev>",
        to: [CONTACT_RECEIVER_EMAIL],
        reply_to: user.email,
        subject: `Ново съобщение от ArchiPari — ${safeTopic}`,
        text:
          `Ново съобщение през контактната форма на ArchiPari\n\n` +
          `От: ${safeName} <${user.email}>\n` +
          `Тема: ${safeTopic}\n\n` +
          `Съобщение:\n${message}`,
      }),
    });

    if (!emailRes.ok) {
      const errText = await emailRes.text();
      console.error("Resend грешка:", emailRes.status, errText);
      return res.status(502).json({ error: "Неуспешно изпращане на имейла. Опитай по-късно." });
    }
  } catch (err) {
    console.error("Грешка при връзка с Resend:", err);
    return res.status(502).json({ error: "Неуспешно изпращане на имейла. Опитай по-късно." });
  }

  return res.status(200).json({ ok: true });
}
