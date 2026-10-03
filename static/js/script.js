// Disable frontend logging - set to false to disable all console logs
const ENABLE_FRONTEND_LOGGING = false;

// Override console methods if logging is disabled
if (!ENABLE_FRONTEND_LOGGING) {
    console.log = function() {};
    console.warn = function() {};
    console.info = function() {};
    console.debug = function() {};
}

const form = document.getElementById("compareForm");
const resultsDiv = document.getElementById("results");

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    resultsDiv.innerHTML = "Scraping reviews from online sources. Please wait...";
    const formData = new FormData(form);
    const response = await fetch("/compare", {method:"POST", body:formData});
    const data = await response.json();
    if(!data.car1 || !data.car2){
        resultsDiv.innerHTML = "<p>No reviews found for one or both cars.</p>";
        return;
    }
    resultsDiv.innerHTML = `
    <h2>Comparison Results</h2>
    <div>
        <h3>${data.car1.car}</h3>
        <p>Total Reviews: ${data.car1.review_count}</p>
        <p>Positive: ${data.car1.sentiment_summary.positive}</p>
        <p>Negative: ${data.car1.sentiment_summary.negative}</p>
        <p>All Reviews:<br>${data.car1.reviews.join("<br><br>")}</p>
    </div>
    <div>
        <h3>${data.car2.car}</h3>
        <p>Total Reviews: ${data.car2.review_count}</p>
        <p>Positive: ${data.car2.sentiment_summary.positive}</p>
        <p>Negative: ${data.car2.sentiment_summary.negative}</p>
        <p>All Reviews:<br>${data.car2.reviews.join("<br><br>")}</p>
    </div>
    `;
});
