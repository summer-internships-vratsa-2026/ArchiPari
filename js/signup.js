(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("signupForm");
    const status = document.getElementById("formStatus");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const fullName = form.fullName.value.trim();
      const email = form.email.value.trim();
      const password = form.password.value;
      const passwordConfirm = form.passwordConfirm.value;

      if (password !== passwordConfirm) {
        status.textContent = "Паролите не съвпадат.";
        status.className = "form-status show error";
        return;
      }
      if (password.length < 6) {
        status.textContent = "Паролата трябва да е поне 6 символа.";
        status.className = "form-status show error";
        return;
      }

      status.textContent = "Регистрация…";
      status.className = "form-status show";

      const { data, error } = await window.ArchiPariAuth.client.auth.signUp({
        email,
        password,
        options: { data: { full_name: fullName } },
      });

      if (error) {
        status.textContent = "Грешка: " + error.message;
        status.className = "form-status show error";
        return;
      }

      // Ако проектът в Supabase изисква потвърждение по имейл, тук няма
      // активна сесия веднага след регистрация — трябва потребителят
      // първо да кликне линка от имейла си.
      if (!data.session) {
        status.textContent = "Регистрацията е успешна! Провери имейла си, за да потвърдиш акаунта, после влез.";
        status.className = "form-status show ok";
        form.reset();
        return;
      }

      status.textContent = "Регистрацията е успешна! Пренасочваме те…";
      status.className = "form-status show ok";
      setTimeout(() => {
        window.location.href = "contact.html";
      }, 800);
    });
  });
})();
