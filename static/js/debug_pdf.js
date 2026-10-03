// Debug version of generateReport function
function generateReportDebug() {
    console.log('DEBUG: Starting PDF report generation...');
    
    // Get current date filter values
    const dateFrom = document.getElementById('dateFrom')?.value;
    const dateTo = document.getElementById('dateTo')?.value;
    
    // Build request data for PDF generation
    const requestData = {
        date_from: dateFrom,
        date_to: dateTo,
        include_charts: true,
        format: 'pdf'
    };
    
    console.log('DEBUG: Request data:', requestData);
    console.log('DEBUG: Current URL:', window.location.href);
    console.log('DEBUG: User logged in:', document.cookie.includes('session'));
    
    showNotification('DEBUG: Generating PDF report...', 'info');
    
    fetch('/generate_report', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(requestData),
        credentials: 'same-origin'  // Include cookies for authentication
    })
    .then(response => {
        console.log('DEBUG: Response status:', response.status);
        console.log('DEBUG: Response headers:', response.headers);
        console.log('DEBUG: Response content-type:', response.headers.get('content-type'));
        console.log('DEBUG: Response URL:', response.url);
        console.log('DEBUG: Response redirected:', response.redirected);
        
        // Check for authentication redirect
        if (response.status === 302 || response.redirected || response.url.includes('/login')) {
            console.error('DEBUG: Authentication required - redirected to login');
            showNotification('Please log in to generate reports. Redirecting to login...', 'error');
            
            // Redirect to login page
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const contentType = response.headers.get('content-type');
        console.log('DEBUG: Processing response with content-type:', contentType);
        
        // Handle cases where content-type is missing or null
        if (!contentType) {
            console.error('DEBUG: Response missing Content-Type header');
            
            // Try to read response as text to get more info
            return response.text().then(text => {
                console.log('DEBUG: Response without content-type (first 500 chars):', text.substring(0, 500));
                
                // Check if it looks like HTML (login page)
                if (text.includes('<html') || text.includes('login') || text.includes('Login')) {
                    console.error('DEBUG: Response appears to be HTML login page');
                    showNotification('Session expired. Please log in again.', 'error');
                    setTimeout(() => {
                        window.location.href = '/login';
                    }, 2000);
                } else if (text.trim() === '') {
                    console.error('DEBUG: Empty response received');
                    showNotification('Server returned empty response. Please try again.', 'error');
                } else if (text.startsWith('{') || text.startsWith('[')) {
                    // Looks like JSON
                    try {
                        const data = JSON.parse(text);
                        const errorMsg = data.error || 'Unknown server error';
                        console.error('DEBUG: JSON error response:', errorMsg);
                        showNotification(`PDF generation failed: ${errorMsg}`, 'error');
                    } catch (parseError) {
                        console.error('DEBUG: Invalid JSON response');
                        showNotification('Server returned invalid response format.', 'error');
                    }
                } else {
                    console.error('DEBUG: Unknown response format without content-type header');
                    showNotification('Server error - unable to determine response type.', 'error');
                }
            }).catch(textError => {
                console.error('DEBUG: Could not read response text:', textError);
                showNotification('Network error - unable to read server response.', 'error');
            });
        }
        
        if (contentType.includes('application/pdf')) {
            console.log('DEBUG: Received PDF response, downloading...');
            return response.blob().then(blob => {
                console.log('DEBUG: PDF blob size:', blob.size, 'bytes');
                
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                const companyName = (window.companyName || 'Company').replace(/\s+/g, '_');
                const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
                const dateRange = dateFrom && dateTo ? `_${dateFrom}_to_${dateTo}` : '';
                
                a.download = `${companyName}_Analytics_Report${dateRange}_${timestamp}.pdf`;
                console.log('DEBUG: Download filename:', a.download);
                
                a.click();
                URL.revokeObjectURL(url);
                
                console.log('DEBUG: PDF download initiated successfully');
                showNotification('PDF report generated and downloaded!', 'success');
            });
        } else if (contentType.includes('text/html')) {
            // Handle HTML response - likely login page
            console.error('DEBUG: Received HTML instead of PDF - probably login page');
            return response.text().then(html => {
                if (html.includes('login') || html.includes('Login')) {
                    console.error('DEBUG: Confirmed - received login page');
                    showNotification('Session expired. Please log in again.', 'error');
                    setTimeout(() => {
                        window.location.href = '/login';
                    }, 2000);
                } else {
                    console.log('DEBUG: HTML response (first 500 chars):', html.substring(0, 500));
                    showNotification('PDF generation failed - received HTML instead of PDF', 'error');
                }
            });
        } else if (contentType.includes('application/json')) {
            // Handle JSON response - backend error
            console.error('DEBUG: Received JSON instead of PDF - backend error');
            return response.json().then(data => {
                console.log('DEBUG: JSON response data:', data);
                
                const errorMsg = data.error || 'Unknown error';
                console.error('DEBUG: Backend error:', errorMsg);
                showNotification(`PDF generation failed: ${errorMsg}`, 'error');
            });
        } else {
            // Handle unexpected content types (not null, but not PDF/HTML/JSON)
            console.error('DEBUG: Expected PDF but got unexpected content type:', contentType);
            return response.text().then(text => {
                console.log('DEBUG: Response text (first 500 chars):', text.substring(0, 500));
                showNotification(`PDF generation failed - unexpected response format: ${contentType}`, 'error');
            });
        }
    })
    .catch(error => {
        console.error('DEBUG: Fetch error:', error);
        showNotification(`Request failed: ${error.message}`, 'error');
    });
}

// Add debug button to page
document.addEventListener('DOMContentLoaded', function() {
    const actionButtons = document.querySelector('.action-buttons');
    if (actionButtons) {
        const debugButton = document.createElement('button');
        debugButton.className = 'action-btn secondary';
        debugButton.innerHTML = '<span>DEBUG</span><span>Debug PDF</span>';
        debugButton.onclick = generateReportDebug;
        actionButtons.appendChild(debugButton);
        console.log('DEBUG: Debug button added to page');
    }
});