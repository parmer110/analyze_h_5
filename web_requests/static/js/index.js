document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tooltip').forEach(item => {
        item.addEventListener('click', event => {
            const url = item.getAttribute('data-url');
            const method = item.getAttribute('data-method');
            const headers = JSON.parse(item.getAttribute('data-header'));
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