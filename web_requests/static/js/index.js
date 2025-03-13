    function getCSRFToken(){
        const cookies = document.cookie.split("; ");
        let cookie = [];
        for (i = 0; i < cookies.length; i++) {
            cookie = cookies[i].split("=");
            if (cookie[0]==="csrftoken") {
                return cookie[1];
            }
        }
    }
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tooltip').forEach(item => {
        item.addEventListener('click', event => {
            const url = item.getAttribute('data-url');
            const method = item.getAttribute('data-method');
            const headers = JSON.parse(item.getAttribute('data-header'));
            headers['X-CSRFToken'] = getCSRFToken();
            const body = item.getAttribute('data-body');

            console.log(url)
            fetch(url, {
                method: method,
                headers: headers,
                body: body
            })
            .then(response => response.json())
            .then(data => console.log(data))
            .catch(error => console.error('Error:', error));
        });
    });
});