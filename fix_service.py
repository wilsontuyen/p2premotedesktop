with open('windows_service_loop.py', 'a', encoding='utf-8') as f:
    f.write('''        except Exception as e:
            log(f"Lỗi trong vòng lặp chính: {e}\\n{traceback.format_exc()}")

        time.sleep(1)

if __name__ == '__main__':
    main()
''')
