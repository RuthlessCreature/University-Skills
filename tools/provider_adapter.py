"""Explicit provider transport. Skill instructions never contain credentials.

No implicit provider/model substitution and no MiniMax fallback.
"""
from dataclasses import dataclass
import json,os,time,urllib.request,urllib.error,urllib.parse

class ProviderError(RuntimeError):
    def __init__(self,status,detail):
        super().__init__(detail);self.status=status

@dataclass
class ProviderConfig:
    provider:str
    model:str
    base_url:str
    key_env:str
    timeout_seconds:int=90
    max_output_tokens:int=4096

    @classmethod
    def load(cls,path):
        with open(path,encoding='utf-8') as f:obj=json.load(f)
        config=cls(**obj)
        if config.provider.lower()=='minimax':raise ProviderError('DISABLED','MiniMax execution is disabled by the workspace instructions.')
        if config.provider not in ('deepseek','openai-compatible'):raise ProviderError('INVALID_CONFIG','Unknown adapter. Choose an implemented protocol explicitly.')
        url=urllib.parse.urlparse(config.base_url)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ProviderError('INVALID_CONFIG','The API base must be HTTPS and must not contain credentials, a query or a fragment.')
        if config.provider=='deepseek' and (url.hostname!='api.deepseek.com' or url.path.rstrip('/') not in ('','/v1')):
            raise ProviderError('INVALID_CONFIG','DeepSeek requires its official API base.')
        if not config.model or not config.key_env or not 1<=config.timeout_seconds<=180 or not 256<=config.max_output_tokens<=16384:
            raise ProviderError('INVALID_CONFIG','Check model, key environment name and request limits.')
        return config

class ChatCompletionsAdapter:
    def __init__(self,config):self.config=config

    def preflight(self):
        c=self.config
        return {'provider':c.provider,'model':c.model,'protocol':'chat-completions','status':'CONFIGURED_UNTESTED' if os.environ.get(c.key_env) else 'NOT_CONFIGURED','key_environment_name':c.key_env,'network_called':False,'codex_compatibility':'NOT_ESTABLISHED','fallback_provider':None}

    def complete(self,messages,tools,record):
        c=self.config;key=os.environ.get(c.key_env)
        if not key:raise ProviderError('NOT_CONFIGURED','Set the configured API key environment variable locally; do not put it in prompts or files.')
        body={'model':c.model,'messages':messages,'tools':tools,'stream':False,'max_tokens':c.max_output_tokens}
        # Explicit non-thinking mode avoids assuming cross-provider reasoning history formats.
        if c.provider=='deepseek':body['thinking']={'type':'disabled'}
        encoded=json.dumps(body,ensure_ascii=False).encode('utf-8')
        for attempt in range(3):
            record({'event':'provider_request','provider':c.provider,'model':c.model,'attempt':attempt+1,'message_count':len(messages),'request_bytes':len(encoded)})
            request=urllib.request.Request(c.base_url.rstrip('/')+'/chat/completions',data=encoded,headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
            try:
                with urllib.request.urlopen(request,timeout=c.timeout_seconds) as res:
                    data=json.loads(res.read().decode('utf-8'))
                choice=data['choices'][0];message=choice['message']
                if choice.get('finish_reason')=='length':raise ProviderError('TRUNCATED','Response reached the configured output limit; partial content was not accepted.')
                if message.get('role')!='assistant':raise ProviderError('PROTOCOL_ERROR','Response did not contain an assistant message.')
                record({'event':'provider_response','provider':c.provider,'model_reported':data.get('model'),'usage':data.get('usage'),'finish_reason':choice.get('finish_reason'),'message':message})
                return message
            except urllib.error.HTTPError as e:
                # Error bodies and request headers are deliberately not included in public logs.
                record({'event':'provider_error','http_status':e.code,'attempt':attempt+1})
                if e.code not in (408,429,500,502,503,504) or attempt==2:raise ProviderError('HTTP_ERROR',f'Provider returned HTTP {e.code}.') from None
            except (urllib.error.URLError,TimeoutError) as e:
                record({'event':'provider_error','error_type':type(e).__name__,'attempt':attempt+1})
                if attempt==2:raise ProviderError('NETWORK_ERROR','Provider connection failed after three attempts.') from None
            except (KeyError,IndexError,ValueError,TypeError):raise ProviderError('PROTOCOL_ERROR','Provider returned an invalid Chat Completions payload.') from None
            time.sleep(1+attempt)
