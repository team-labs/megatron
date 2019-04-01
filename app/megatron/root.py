from django.http import HttpResponse


def root(request):
    megatron_text = """
<style>
    body {
        background-color: black;
        color: red;
    }
</style>
<pre>
                                _                   
                               | |                  
     _ __ ___   ___  __ _  __ _| |_ _ __ ___  _ __  
    | '_ ` _ \ / _ \/ _` |/ _` | __| '__/ _ \| '_ \ 
    | | | | | |  __/ (_| | (_| | |_| | | (_) | | | |
    |_| |_| |_|\___|\__, |\__,_|\__|_|  \___/|_| |_|
                     __/ |                         
                    |___/                         
                    
    Your Megatron app is running!
</pre>
    """
    return HttpResponse(megatron_text, content_type="text/html")


