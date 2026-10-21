/**
 * Quiz Form Submission and Congratulations Modal Handling
 */

document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("quizForm");
  if (!form) return;

  const submitBtn = document.getElementById("submitQuizBtn");
  const congratsModal = document.getElementById("congratsModal");
  const modalOkBtn = document.getElementById("modalOkBtn");
  const errorAlert = document.getElementById("quizErrorAlert");

  form.addEventListener("submit", function (e) {
    e.preventDefault();

    // Collect answers
    const answers = {};
    const questionBlocks = document.querySelectorAll(".question-block");
    let missingQuestion = null;

    questionBlocks.forEach(block => {
      const qid = block.getAttribute("data-question-id");
      const selected = block.querySelector(`input[name="q${qid}"]:checked`);
      if (selected) {
        answers[qid] = selected.value;
      } else if (!missingQuestion) {
        missingQuestion = qid;
      }
    });

    if (missingQuestion) {
      if (errorAlert) {
        errorAlert.textContent = `Please select an answer for all 5 questions before submitting (Question ${missingQuestion} is unanswered).`;
        errorAlert.style.display = "block";
      }
      const missingBlock = document.getElementById(`question-${missingQuestion}`);
      if (missingBlock) {
        missingBlock.scrollIntoView({ behavior: "smooth", block: "center" });
        missingBlock.style.borderColor = "#ef4444";
      }
      return;
    }

    if (errorAlert) {
      errorAlert.style.display = "none";
    }

    // Set submitting flag to prevent beforeunload beacon
    if (window.markQuizAsSubmitting) {
      window.markQuizAsSubmitting();
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Verifying Responses...</span>`;

    fetch("/api/quiz/submit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ answers: answers })
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          // Success: Display Congratulations popup modal!
          if (congratsModal) {
            congratsModal.classList.add("active");
            if (modalOkBtn) {
              modalOkBtn.addEventListener("click", function () {
                window.location.href = data.redirect || "/stage?revealed=true";
              });
            }
          } else {
            alert(data.message || "Congratulations! You answered all 5 questions correctly.");
            window.location.href = data.redirect || "/stage?revealed=true";
          }
        } else {
          // Failure Condition: Immediately redirected to 'Access Revoked / Game Over' screen
          window.location.href = data.redirect || "/disqualified";
        }
      })
      .catch(err => {
        console.error("Submission error:", err);
        window.location.href = "/disqualified";
      });
  });
});
