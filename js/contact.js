(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", async () => {
    const form = document.getElementById("contactForm");
    const gate = document.getElementById("authGate");
    const status = document.getElementById("formStatus");
    const accountNote = document.getElementById("accountNote");
    if (!form || !window.ArchiPariAuth) return;

    const session = await window.ArchiPariAuth.getSession();

    if (!session) {
      form.style.display = "none";
      if (gate) gate.style.display = "block";
      return;
    }

    form.style.display = "";
    if (gate) gate.style.display = "none";

    if (accountNote) {
      const email = session.user.email || "";
      accountNote.textContent = `Ще изпратим съобщението от твоя акаунт: ${email}`;
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      // Honeypot - ако е попълнено, значи е бот; преструваме се, че сме
      // изпратили успешно, без реално да пращаме имейл.
      if (form.website && form.website.value) {
        status.textContent = "Съобщението е изпратено успешно!";
        status.className = "form-status show ok";
        form.reset();
        return;
      }

      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;
      status.textContent = "Изпращане…";
      status.className = "form-status show";

      // Взимаме прясна сесия при всяко изпращане (токънът може да е изтекъл,
      // ако формата е стояла отворена дълго време).
      const freshSession = await window.ArchiPariAuth.getSession();
      if (!freshSession) {
        status.textContent = "Сесията ти е изтекла — влез отново.";
        status.className = "form-status show error";
        if (submitBtn) submitBtn.disabled = false;
        form.style.display = "none";
        if (gate) gate.style.display = "block";
        return;
      }

      try {
        const res = await fetch("/api/contact", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${freshSession.access_token}`,
          },
          body: JSON.stringify({
            topic: form.topic.value,
            message: form.message.value,
          }),
        });

        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
          throw new Error(data.error || `Грешка (код ${res.status})`);
        }

        status.textContent = "Съобщението е изпратено успешно! Ще се свържем с теб скоро.";
        status.className = "form-status show ok";
        form.reset();
        if (accountNote) {
          accountNote.textContent = `Ще изпратим съобщението от твоя акаунт: ${session.user.email || ""}`;
        }
      } catch (err) {
        status.textContent = "Възникна грешка: " + err.message;
        status.className = "form-status show error";
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  });
})();
