
<#-- Keycloak login.ftl styled to match Django login page with Tailwind-like CSS classes inline -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Login - DI4D Portal</title>
    <link rel="stylesheet" type="text/css" href="https://di4d.davidmaat.be/static/css/dist/styles.css">
    <link rel="stylesheet" type="text/css" href="https://di4d.davidmaat.be/static/style.css">
    <script src="https://cdn.jsdelivr.net/npm/@tailwindplus/elements@1" type="module"></script>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
<div class="min-h-screen bg-[var(--blue_di4d)] flex flex-col items-center justify-center px-4 py-12 gap-8">
    <img class="rounded-full object-cover w-50 h-50 md:w-60 md:h-60 mx-auto p-5" src="${url.resourcesPath}/images/DI4D.png" alt="DI4D Logo">
    <h1 class="text-white text-2xl md:text-3xl font-bold text-center">Login DI4D</h1>
    <form id="kc-form-login" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post" class="w-full max-w-sm space-y-4 flex flex-col items-start">
        <#if csrfToken??>
            <input type="hidden" name="csrf_token" value="${csrfToken}">
        </#if>
        <label for="username" class="text-white text-sm font-medium w-full text-left">Username</label>
        <input placeholder="Username" type="text" id="username" name="username" required class="w-full px-4 py-2 rounded-md border bg-white text-gray-900" value="${username!""}">
        <label for="password" class="text-white text-sm font-medium w-full text-left">Password</label>
        <input placeholder="Password" type="password" id="password" name="password" required class="w-full px-4 py-2 rounded-md border bg-white text-gray-900">
        <a href="${url.loginResetCredentialsUrl}" class="text-white underline">Forgot Password?</a>
        <#if message?has_content && message.type == "error">
            <p class="w-full bg-red-500 text-white text-sm px-3 py-2 rounded mb-2">
                ${message.summary}
            </p>
        </#if>
        <input class="btn_primary_orange mx-auto" type="submit" name="login" value="Login">
    </form>
</div>
</body>
</html>
