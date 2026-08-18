// // START ASSESSMENT
// async function startAssessment() {
//     const response = await fetch("http://127.0.0.1:8000/api/analyze/", {
//         method: "POST",
//         headers: {
//             "Content-Type": "application/json"
//         },
//         body: JSON.stringify({
//             user_id: 1,
//             symptoms: ["fever", "headache"]
//         })
//     });

//     const data = await response.json();

//     alert(`Disease: ${data.disease}\nRisk: ${data.risk}`);
// }


// // CHATBOT
// async function sendMessage() {
//     const input = document.getElementById("chatInput");
//     const message = input.value;

//     const response = await fetch("http://127.0.0.1:8000/api/chatbot/", {
//         method: "POST",
//         headers: {
//             "Content-Type": "application/json"
//         },
//         body: JSON.stringify({
//             message: message
//         })
//     });

//     const data = await response.json();

//     const chatBox = document.getElementById("chatBox");

//     chatBox.innerHTML += `<p><b>You:</b> ${message}</p>`;
//     chatBox.innerHTML += `<p><b>Bot:</b> ${data.reply}</p>`;

//     input.value = "";
// }

// ================================
// START ASSESSMENT BUTTON
// ================================
function startAssessment() {
    window.location.href = "member_assessment.html";
}


// ================================
// ANALYZE SYMPTOMS (CALL BACKEND)
// ================================
async function analyzeSymptoms() {
    const inputElement = document.getElementById("symptoms");
    const resultDiv = document.getElementById("results");

    const input = inputElement.value.trim();

    if (!input) {
        alert("Please enter symptoms");
        return;
    }

    // Convert input to array
    const symptomsArray = input
        .split(",")
        .map(s => s.trim().toLowerCase())
        .filter(s => s.length > 0);

    // Show loading
    resultDiv.innerHTML = "<p>Analyzing symptoms... ⏳</p>";

    try {
        const response = await fetch("http://127.0.0.1:8000/api/analyze/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                symptoms: symptomsArray
            })
        });

        if (!response.ok) {
            throw new Error("Server error");
        }

        const data = await response.json();

        displayResults(data);

    } catch (error) {
        console.error("Error:", error);
        resultDiv.innerHTML = "<p style='color:red;'>Error connecting to server</p>";
    }
}


// ================================
// DISPLAY RESULTS ON UI
// ================================
function displayResults(results) {
    const resultDiv = document.getElementById("results");
    resultDiv.innerHTML = "";

    if (!results || results.length === 0) {
        resultDiv.innerHTML = "<p>No matching disease found</p>";
        return;
    }

    results.forEach(disease => {
        const card = document.createElement("div");

        card.style.border = "1px solid #ddd";
        card.style.borderRadius = "8px";
        card.style.padding = "12px";
        card.style.margin = "10px 0";
        card.style.backgroundColor = "#f9f9f9";

        card.innerHTML = `
            <h3 style="margin:0;">${disease.disease}</h3>
            <p><strong>Risk Score:</strong> ${disease.score}%</p>
            <p><strong>Precautions:</strong> ${Array.isArray(disease.precautions) 
                ? disease.precautions.join(", ") 
                : disease.precautions}</p>
        `;

        resultDiv.appendChild(card);
    });
}


// ================================
// OPTIONAL: ENTER KEY SUPPORT
// ================================
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("symptoms");

    if (input) {
        input.addEventListener("keypress", function (e) {
            if (e.key === "Enter") {
                analyzeSymptoms();
            }
        });
    }
});