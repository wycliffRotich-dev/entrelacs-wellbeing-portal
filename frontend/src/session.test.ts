import { clearToken, getToken, setToken } from "./session";

test("token round-trips and clears", () => {
  expect(getToken()).toBeNull();
  setToken("abc");
  expect(getToken()).toBe("abc");
  clearToken();
  expect(getToken()).toBeNull();
});
