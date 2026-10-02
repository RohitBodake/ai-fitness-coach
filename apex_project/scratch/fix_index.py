import os

file_path = 'templates/index.html'
if not os.path.exists(file_path):
    print(f"File {file_path} not found")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

heartbeat_func = """
let heartbeatInterval = null;
function startHeartbeat() {
  if (heartbeatInterval) clearInterval(heartbeatInterval);
  const uid = getCurrentUser();
  const users = getUsers();
  if (!users[uid]) return;

  const ping = async () => {
    try {
      await fetch('/heartbeat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: users[uid].email })
      });
    } catch (e) {}
  };
  ping();
  heartbeatInterval = setInterval(ping, 60000);
}
"""

if '</script>' in content:
    # Replace the last occurrence of </script>
    parts = content.rsplit('</script>', 1)
    new_content = parts[0] + heartbeat_func + '</script>' + parts[1]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully added heartbeat function to index.html")
else:
    print("Could not find </script> tag in index.html")
