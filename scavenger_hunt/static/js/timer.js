/**
 * Precision 2-Minute Countdown Timer & Abandonment Guard
 */

(function () {
  const timerElement = document.getElementById("timerDigits");
  const timerProgressBar = document.getElementById("timerProgressBar");
  const timerContainer = document.getElementById("timerContainer");
  const quizForm = document.getElementById("quizForm");

  if (!timerElement) return;

  const totalDuration = parseInt(timerElement.getAttribute("data-time-limit"), 10) || 120;
  let remainingSeconds = parseInt(timerElement.getAttribute("data-remaining"), 10) || totalDuration;
  let timerExpired = false;
  let isSubmitting = false;

  window.markQuizAsSubmitting = function () {
    isSubmitting = true;
  };

  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }

  function updateDisplay() {
    timerElement.textContent = formatTime(remainingSeconds);

    const percentage = Math.max(0, (remainingSeconds / totalDuration) * 100);
    if (timerProgressBar) {
      timerProgressBar.style.width = percentage + "%";
    }

    if (remainingSeconds <= 20) {
      timerContainer.classList.remove("timer-warning");
      timerContainer.classList.add("timer-danger");
      if (timerProgressBar) {
        timerProgressBar.style.background = "#ef4444";
      }
    } else if (remainingSeconds <= 45) {
      timerContainer.classList.add("timer-warning");
      if (timerProgressBar) {
        timerProgressBar.style.background = "#f59e0b";
      }
    } else {
      timerContainer.classList.remove("timer-warning", "timer-danger");
      if (timerProgressBar) {
        timerProgressBar.style.background = "linear-gradient(90deg, #06b6d4, #3b82f6)";
      }
    }
  }

  updateDisplay();

  const intervalId = setInterval(function () {
    if (isSubmitting || timerExpired) return;

    remainingSeconds--;

    if (remainingSeconds <= 0) {
      remainingSeconds = 0;
      updateDisplay();
      clearInterval(intervalId);
      timerExpired = true;
      handleTimeout();
    } else {
      updateDisplay();
    }
  }, 1000);

  function handleTimeout() {
    // Disable all inputs
    if (quizForm) {
      const inputs = quizForm.querySelectorAll("input, button");
      inputs.forEach(el => el.disabled = true);
    }

    // Notify backend of timeout
    fetch("/api/quiz/timeout", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    })
      .then(res => res.json())
      .then(data => {
        window.location.href = data.redirect || "/disqualified";
      })
      .catch(() => {
        window.location.href = "/disqualified";
      });
  }

  // Abandonment Detection: If user leaves, closes, or reloads before submitting
  window.addEventListener("beforeunload", function (e) {
    if (!isSubmitting && !timerExpired) {
      // Send beacon immediately to server to mark user as disqualified_timeout
      navigator.sendBeacon("/api/quiz/abandon");
    }
  });

})();
