# GitHub Push via SSH

이 문서는 OpenClaw 서버에서 GitHub 저장소로 `git push` 할 때 필요한 SSH 연결 절차를 정리한다.

## 상황

- 원격 URL은 보통 `git@github.com:<owner>/<repo>.git` 형태다.
- `git push` 가 `Host key verification failed` 또는 `Permission denied (publickey)` 로 실패할 수 있다.

## 1. SSH 디렉터리 확인

```bash
ls -al ~/.ssh
```

확인할 파일:

- `known_hosts`
- `id_ed25519`
- `id_ed25519.pub`

## 2. SSH 키 생성

키가 없으면 새로 만든다.

```bash
ssh-keygen -t ed25519 -C "jeonghanyun_@openclaw" -f ~/.ssh/id_ed25519 -N ""
```

권장 사항:

- 기본 경로 `~/.ssh/id_ed25519` 를 사용한다.
- passphrase 는 필요하면 넣어도 되지만, 자동화 서버에서는 비워 두는 경우도 많다.

## 3. ssh-agent 등록

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

## 4. 공개키 확인

GitHub에 등록할 공개키를 출력한다.

```bash
cat ~/.ssh/id_ed25519.pub
```

출력 예:

```text
ssh-ed25519 AAAA... comment
```

이 한 줄 전체를 GitHub의 SSH key 등록창에 붙여넣는다.

## 5. GitHub에 등록

GitHub 웹에서:

- Settings
- SSH and GPG keys
- New SSH key

입력값:

- Title: `openclaw-workspace` 같은 식으로 구분되게
- Key: `cat ~/.ssh/id_ed25519.pub` 출력 전체

## 6. 연결 테스트

```bash
ssh -T git@github.com
```

성공하면 대개 이런 식의 메시지가 나온다.

```text
Hi <username>! You've successfully authenticated, but GitHub does not provide shell access.
```

## 7. known_hosts 오류 해결

처음 연결할 때 host key 확인이 안 되어 실패하면 아래를 실행한다.

```bash
mkdir -p ~/.ssh
ssh-keyscan github.com >> ~/.ssh/known_hosts
```

그 다음 다시 테스트한다.

```bash
ssh -T git@github.com
```

## 8. push

인증이 되면 저장소에서 푸시한다.

```bash
git -C /home/openclaw/projects/graphrag-eval push origin main
```

## 9. 실패 유형

### `Host key verification failed`

- `known_hosts` 에 GitHub 호스트 키가 없을 때 주로 발생한다.
- `ssh-keyscan github.com >> ~/.ssh/known_hosts` 로 복구한다.

### `Permission denied (publickey)`

- 공개키가 GitHub에 등록되지 않았거나
- 로컬에 올린 개인키와 GitHub에 등록한 공개키가 짝이 안 맞을 때 발생한다.
- `ssh-add ~/.ssh/id_ed25519` 후 다시 `ssh -T git@github.com` 를 확인한다.

## 10. 이 저장소에서 확인된 값

이 프로젝트에서 실제로 사용한 공개키는 다음과 같다.

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILFlGKeOxTq201SEdl2d74anVsJa4/YMIdO64uodNGo2 jeonghanyun_@openclaw
```

## 11. 권장 흐름

1. `~/.ssh` 상태 확인
2. 새 `ed25519` 키 생성
3. `ssh-agent` 에 등록
4. 공개키를 GitHub에 등록
5. `ssh -T git@github.com` 로 검증
6. `git push`
