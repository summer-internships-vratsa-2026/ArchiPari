/* =========================================================
   auth.js — автентикация с имейл/парола чрез Supabase
   ========================================================= */

// ⚠️ ЗАДЪЛЖИТЕЛНО ПОПЪЛНИ ТЕЗИ ДВЕ СТОЙНОСТИ — виж AUTH_SETUP.md
// за точните стъпки как да си създадеш безплатен Supabase проект.
// SUPABASE_ANON_KEY е ПУБЛИЧЕН ключ по дизайн (не е тайна) — нормално е
// да стои във фронтенд кода, не е нужно да се крие в environment variable.
const SUPABASE_URL = "https://xfvdcnldnolrmiuqfzej.supabase.co"; // TODO
const SUPABASE_ANON_KEY = "sb_publishable_xEt1q9EN7ThuUHVadTVjXw_qnJYD2gy"; // TODO

(function () {
  "use strict";

  if (!window.supabase || !window.supabase.createClient) {
    console.error("Supabase SDK не се зареди (провери интернет връзката / CDN линка).");
    return;
  }

  const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  async function getSession() {
    const { data, error } = await sb.auth.getSession();
    if (error) {
      console.error("Грешка при проверка на сесията:", error.message);
      return null;
    }
    return data.session;
  }

  async function logout() {
    await sb.auth.signOut();
    window.location.href = "index.html";
  }

  // Излагаме глобално, за да го ползват login.html, signup.html, contact.html
  window.ArchiPariAuth = {
    client: sb,
    getSession,
    logout,
  };

  // Обновяваме навигацията (Вход/Регистрация или Изход) на всяка страница,
  // в която има <span id="authNav">.
  document.addEventListener("DOMContentLoaded", async () => {
    const el = document.getElementById("authNav");
    if (!el) return;

    const session = await getSession();
    if (session && session.user) {
      const email = session.user.email || "";
      el.innerHTML = `<span class="auth-email" title="${email}">${email}</span> · <a href="#" id="authLogoutLink">Изход</a>`;
      const link = document.getElementById("authLogoutLink");
      if (link) {
        link.addEventListener("click", (e) => {
          e.preventDefault();
          logout();
        });
      }
    } else {
      el.innerHTML = `<a href="login.html">Вход</a> · <a href="signup.html">Регистрация</a>`;
    }
  });
})();
