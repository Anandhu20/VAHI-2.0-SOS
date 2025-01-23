// auth.js
let currentUser = null;

function showLogin() {
    document.getElementById('register-form').style.display = 'none';
    document.getElementById('login-form').style.display = 'block';
}

function showRegister() {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'block';
}

function showMainContent() {
    document.getElementById('auth-container').style.display = 'none';
    document.getElementById('main-content').style.display = 'block';
    document.getElementById('user-email').textContent = currentUser.email;
}

async function login() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    try {
        const response = await fetch('http://localhost:5000/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, app_password: password }),
            credentials: 'include'
        });

        const data = await response.json();
        if (data.success) {
            currentUser = data.user;
            showMainContent();
        } else {
            alert(data.message);
        }
    } catch (error) {
        alert('Login failed: ' + error.message);
    }
}

async function register() {
    const name = document.getElementById('register-name').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const latitude = document.getElementById('register-latitude').value;
    const longitude = document.getElementById('register-longitude').value;

    try {
        const response = await fetch('http://localhost:5000/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name,
                email,
                app_password: password,
                latitude,
                longitude
            })
        });

        const data = await response.json();
        if (data.success) {
            alert('Registration successful! Please login.');
            showLogin();
        } else {
            alert(data.message);
        }
    } catch (error) {
        alert('Registration failed: ' + error.message);
    }
}

async function logout() {
    try {
        await fetch('http://localhost:5000/logout', {
            method: 'POST',
            credentials: 'include'
        });
        currentUser = null;
        document.getElementById('main-content').style.display = 'none';
        document.getElementById('auth-container').style.display = 'block';
        showLogin();
    } catch (error) {
        alert('Logout failed: ' + error.message);
    }
}

// Update the sendDistressSignal function
async function sendDistressSignal() {
    if (!currentUser) {
        alert('Please login first');
        return;
    }

    try {
        const location = await getCurrentLocation();
        
        const response = await fetch('http://localhost:5000/send_sos_email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                latitude: location.latitude,
                longitude: location.longitude,
                recipient_email: 'helper@example.com' // You'll need to get this from your helpers database
            }),
            credentials: 'include'
        });

        const data = await response.json();
        if (data.success) {
            alert('SOS signal sent successfully!');
        } else {
            alert('Failed to send SOS: ' + data.message);
        }
    } catch (error) {
        alert('Error sending SOS: ' + error.message);
    }
}